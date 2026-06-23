from fastapi import APIRouter
from pydantic import BaseModel

from ..bootstrap_sql import ddl_statements, seed_components_sql
from ..config import get_workspace_client, settings
from ..sql import run_sql

router = APIRouter()


class SettingsIn(BaseModel):
    catalog: str | None = None
    schema_name: str | None = None
    warehouse_id: str | None = None
    default_model: str | None = None


@router.get("/settings")
def get_settings():
    warehouses = []
    try:
        for wh in get_workspace_client().warehouses.list():
            warehouses.append({"id": wh.id, "name": wh.name,
                               "state": wh.state.value if wh.state else None})
    except Exception:
        pass
    return {**settings.as_dict(), "warehouses": warehouses}


@router.patch("/settings")
def update_settings(body: SettingsIn):
    settings.update(
        catalog=body.catalog,
        schema=body.schema_name,
        warehouse_id=body.warehouse_id,
        default_model=body.default_model,
    )
    return settings.as_dict()


@router.post("/bootstrap")
def bootstrap():
    """Create the schema + Delta tables and seed the component catalog (idempotent)."""
    run_sql(f"CREATE SCHEMA IF NOT EXISTS {settings.fq_schema}")
    for tmpl in ddl_statements():
        run_sql(tmpl.format(
            components=settings.table("vsu_components"),
            configs=settings.table("vsu_configs"),
            runs=settings.table("vsu_runs"),
            run_results=settings.table("vsu_run_results"),
        ))
    run_sql(seed_components_sql(settings.table("vsu_components")))
    return {"ok": True, "schema": f"{settings.catalog}.{settings.schema}"}
