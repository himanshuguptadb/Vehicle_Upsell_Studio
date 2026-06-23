from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import get_workspace_client, get_workspace_host, settings
from ..sql import run_sql, sql_str, SqlError

router = APIRouter()

SAMPLE_TABLES = ["customer", "vehicle", "technician", "service"]


class GenIn(BaseModel):
    rows: int = 300
    model: str | None = None


def _notebook_path(name: str) -> str:
    base = settings.jobs_workspace_dir.rstrip("/")
    if not base:
        raise HTTPException(400, "JOBS_WORKSPACE_DIR not set; redeploy with the setup script")
    return f"{base}/{name}"


@router.get("/sample/status")
def sample_status():
    """Which sample tables exist and their row counts."""
    try:
        present = {
            r["table_name"].lower()
            for r in run_sql(
                f"SELECT table_name FROM `{settings.catalog}`.information_schema.tables "
                f"WHERE lower(table_schema) = {sql_str(settings.schema.lower())}"
            )
        }
    except SqlError:
        present = set()
    out = {}
    for t in SAMPLE_TABLES:
        if t in present:
            try:
                cnt = run_sql(f"SELECT count(*) AS n FROM {settings.table(t)}")[0]["n"]
                out[t] = int(cnt)
            except SqlError:
                out[t] = None
        else:
            out[t] = None
    return {"tables": out, "ready": all(out.get(t) for t in SAMPLE_TABLES)}


@router.post("/sample/generate")
def generate_sample(body: GenIn):
    from databricks.sdk.service import jobs

    w = get_workspace_client()
    run = w.jobs.submit(
        run_name="vsu_generate_sample_data",
        tasks=[
            jobs.SubmitTask(
                task_key="generate",
                notebook_task=jobs.NotebookTask(
                    notebook_path=_notebook_path("generate_sample_data"),
                    base_parameters={
                        "catalog": settings.catalog,
                        "schema": settings.schema,
                        "rows": str(body.rows),
                        "model": body.model or settings.default_model,
                    },
                ),
            )
        ],
    )
    run_id = run.run_id
    return {"run_id": run_id, "url": f"{get_workspace_host()}/jobs/runs/{run_id}"}


@router.get("/sample/run-status")
def run_status(run_id: int):
    w = get_workspace_client()
    r = w.jobs.get_run(run_id=run_id)
    life = r.state.life_cycle_state.value if r.state and r.state.life_cycle_state else None
    result = r.state.result_state.value if r.state and r.state.result_state else None
    return {"life_cycle_state": life, "result_state": result}
