import json
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..aiquery import distribution, run_config
from ..config import settings
from ..sql import run_sql, sql_str

router = APIRouter()


class RunIn(BaseModel):
    model: str
    prompt_text: str
    components: list[dict] = []
    source_table: str = "service"
    limit: int = 50
    persist: bool = False
    config_id: str | None = None
    config_name: str = "(draft)"


class ConfigRef(BaseModel):
    # Either reference a saved config by id, or pass an inline draft.
    config_id: str | None = None
    label: str = ""
    model: str | None = None
    prompt_text: str | None = None
    components: list[dict] | None = None


class CompareIn(BaseModel):
    a: ConfigRef
    b: ConfigRef
    source_table: str = "service"
    limit: int = 50


def _persist_run(rows: list[dict], *, config_id, config_name, model, source_table, limit):
    run_id = uuid.uuid4().hex
    run_sql(f"""
INSERT INTO {settings.table('vsu_runs')}
  (run_id, config_id, config_name, model_endpoint, source_table, row_count, created_at)
VALUES ({sql_str(run_id)}, {sql_str(config_id or '')}, {sql_str(config_name)},
        {sql_str(model)}, {sql_str(source_table)}, {int(limit)}, current_timestamp())
""")
    if rows:
        values = ",\n".join(
            f"({sql_str(run_id)}, {int(r.get('service_id') or 0)}, "
            f"{sql_str(r.get('component_key'))}, {sql_str(r.get('classification'))}, "
            f"{sql_str(r.get('reasoning'))})"
            for r in rows
        )
        run_sql(
            f"INSERT INTO {settings.table('vsu_run_results')} "
            f"(run_id, service_id, component_key, classification, reasoning) VALUES {values}"
        )
    return run_id


@router.post("/run")
def run(body: RunIn):
    if not body.components:
        raise HTTPException(400, "select at least one component")
    rows = run_config(model=body.model, prompt_text=body.prompt_text,
                      components=body.components, source_table=body.source_table,
                      limit=body.limit)
    for r in rows:
        r["service_id"] = int(r["service_id"]) if r.get("service_id") is not None else None
        # Statement Execution returns booleans as 'true'/'false' strings.
        tf = r.get("technician_flagged")
        r["technician_flagged"] = tf in (True, "true", "True", 1, "1")
    out = {"rows": rows, "distribution": distribution(rows)}
    if body.persist:
        out["run_id"] = _persist_run(rows, config_id=body.config_id,
                                     config_name=body.config_name, model=body.model,
                                     source_table=body.source_table, limit=body.limit)
    return out


def _resolve(ref: ConfigRef) -> tuple[str, str, list[dict], str]:
    if ref.config_id:
        rows = run_sql(
            f"SELECT name, model_endpoint, prompt_text, components "
            f"FROM {settings.table('vsu_configs')} WHERE config_id = {sql_str(ref.config_id)}"
        )
        if not rows:
            raise HTTPException(404, f"config {ref.config_id} not found")
        r = rows[0]
        comps = json.loads(r.get("components") or "[]")
        label = ref.label or r.get("name") or ref.config_id
        return r["model_endpoint"], r["prompt_text"], comps, label
    if not (ref.model and ref.prompt_text is not None and ref.components is not None):
        raise HTTPException(400, "config ref needs config_id or model+prompt+components")
    return ref.model, ref.prompt_text, ref.components, (ref.label or "draft")


@router.post("/compare")
def compare(body: CompareIn):
    a_model, a_prompt, a_comps, a_label = _resolve(body.a)
    b_model, b_prompt, b_comps, b_label = _resolve(body.b)

    # Run the two passes concurrently. Each is an independent ai_query statement that blocks on
    # the warehouse, so threads (which release the GIL during the network wait) overlap them and
    # roughly halve the compare wall-clock vs running A then B sequentially.
    def _pass(model, prompt, comps):
        return run_config(model=model, prompt_text=prompt, components=comps,
                          source_table=body.source_table, limit=body.limit)
    with ThreadPoolExecutor(max_workers=2) as ex:
        fa = ex.submit(_pass, a_model, a_prompt, a_comps)
        fb = ex.submit(_pass, b_model, b_prompt, b_comps)
        a_rows = fa.result()
        b_rows = fb.result()

    def index(rows):
        return {(int(r["service_id"]), r["component_key"]): r for r in rows}

    ai, bi = index(a_rows), index(b_rows)
    keys = sorted(set(ai) | set(bi))
    diffs = []
    disagree = 0
    for sid, comp in keys:
        ra, rb = ai.get((sid, comp)), bi.get((sid, comp))
        ca = ra["classification"] if ra else None
        cb = rb["classification"] if rb else None
        differs = ca != cb
        if differs:
            disagree += 1
        notes = (ra or rb or {}).get("service_performed")
        diffs.append({
            "service_id": sid, "component_key": comp,
            "service_performed": notes,
            "a_classification": ca, "a_reasoning": ra["reasoning"] if ra else None,
            "b_classification": cb, "b_reasoning": rb["reasoning"] if rb else None,
            "differs": differs,
        })
    return {
        "a": {"label": a_label, "model": a_model, "prompt": a_prompt, "distribution": distribution(a_rows)},
        "b": {"label": b_label, "model": b_model, "prompt": b_prompt, "distribution": distribution(b_rows)},
        "rows": diffs,
        "total": len(diffs),
        "disagreements": disagree,
    }
