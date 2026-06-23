import json
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..aiquery import RESPONSE_FORMAT
from ..config import settings
from ..sql import run_sql, sql_str

router = APIRouter()


class ConfigIn(BaseModel):
    name: str
    description: str = ""
    model_endpoint: str
    components: list[dict] = []
    prompt_text: str = ""


def _row_to_config(r: dict) -> dict:
    try:
        r["components"] = json.loads(r.get("components") or "[]")
    except (json.JSONDecodeError, TypeError):
        r["components"] = []
    return r


@router.get("/configs")
def list_configs():
    rows = run_sql(
        f"SELECT config_id, name, description, model_endpoint, components, prompt_text, "
        f"response_format, created_by, "
        f"CAST(created_at AS STRING) AS created_at, CAST(updated_at AS STRING) AS updated_at "
        f"FROM {settings.table('vsu_configs')} ORDER BY updated_at DESC"
    )
    return [_row_to_config(r) for r in rows]


@router.get("/configs/{config_id}")
def get_config(config_id: str):
    rows = run_sql(
        f"SELECT config_id, name, description, model_endpoint, components, prompt_text, "
        f"response_format, created_by, CAST(created_at AS STRING) AS created_at, "
        f"CAST(updated_at AS STRING) AS updated_at "
        f"FROM {settings.table('vsu_configs')} WHERE config_id = {sql_str(config_id)}"
    )
    if not rows:
        raise HTTPException(404, "config not found")
    return _row_to_config(rows[0])


@router.post("/configs")
def create_config(cfg: ConfigIn):
    config_id = uuid.uuid4().hex
    comps = json.dumps(cfg.components)
    t = settings.table("vsu_configs")
    run_sql(f"""
INSERT INTO {t}
  (config_id, name, description, model_endpoint, components, prompt_text,
   response_format, created_by, created_at, updated_at)
VALUES (
  {sql_str(config_id)}, {sql_str(cfg.name)}, {sql_str(cfg.description)},
  {sql_str(cfg.model_endpoint)}, {sql_str(comps)}, {sql_str(cfg.prompt_text)},
  {sql_str(RESPONSE_FORMAT)}, current_user(), current_timestamp(), current_timestamp()
)
""")
    return {"config_id": config_id}


# Note: there is intentionally no update/overwrite endpoint. Configs are immutable once
# saved — every change is saved as a NEW config so the full history is preserved.


@router.delete("/configs/{config_id}")
def delete_config(config_id: str):
    run_sql(
        f"DELETE FROM {settings.table('vsu_configs')} WHERE config_id = {sql_str(config_id)}"
    )
    return {"ok": True}
