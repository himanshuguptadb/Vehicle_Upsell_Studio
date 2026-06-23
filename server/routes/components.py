from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..sql import run_sql, sql_str

router = APIRouter()


class Component(BaseModel):
    component_key: str
    display_name: str
    description: str = ""
    rubric: str = ""
    enabled: bool = True
    sort_order: int = 100


@router.get("/components")
def list_components():
    rows = run_sql(
        f"SELECT component_key, display_name, description, rubric, enabled, sort_order "
        f"FROM {settings.table('vsu_components')} ORDER BY sort_order, component_key"
    )
    for r in rows:
        r["enabled"] = bool(r.get("enabled") in (True, "true", "True", 1, "1"))
        r["sort_order"] = int(r.get("sort_order") or 0)
    return rows


@router.post("/components")
def upsert_component(c: Component):
    t = settings.table("vsu_components")
    run_sql(f"""
MERGE INTO {t} AS t
USING (SELECT {sql_str(c.component_key)} AS component_key) AS s
ON t.component_key = s.component_key
WHEN MATCHED THEN UPDATE SET
  display_name = {sql_str(c.display_name)},
  description = {sql_str(c.description)},
  rubric = {sql_str(c.rubric)},
  enabled = {str(c.enabled).lower()},
  sort_order = {int(c.sort_order)}
WHEN NOT MATCHED THEN INSERT
  (component_key, display_name, description, rubric, enabled, sort_order)
  VALUES ({sql_str(c.component_key)}, {sql_str(c.display_name)}, {sql_str(c.description)},
          {sql_str(c.rubric)}, {str(c.enabled).lower()}, {int(c.sort_order)})
""")
    return {"ok": True, "component_key": c.component_key}


@router.delete("/components/{component_key}")
def delete_component(component_key: str):
    run_sql(
        f"DELETE FROM {settings.table('vsu_components')} "
        f"WHERE component_key = {sql_str(component_key)}"
    )
    return {"ok": True}
