import re

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..config import get_workspace_client, get_workspace_host, settings
from ..sql import run_sql, sql_str

router = APIRouter()


class DeployIn(BaseModel):
    config_id: str
    run_now: bool = True


def _requesting_user(request: Request) -> str | None:
    """The human who clicked Deploy. Databricks Apps forward the end user's identity in these
    headers; we use it to grant them access to the job (which is otherwise owned only by the
    app's service principal, so non-admins couldn't see it)."""
    for h in ("X-Forwarded-Email", "X-Forwarded-Preferred-Username", "X-Forwarded-User"):
        v = request.headers.get(h)
        if v:
            return v
    return None


def _notebook_path(name: str) -> str:
    base = settings.jobs_workspace_dir.rstrip("/")
    if not base:
        raise HTTPException(400, "JOBS_WORKSPACE_DIR not set; redeploy with the setup script")
    return f"{base}/{name}"


@router.post("/deploy-job")
def deploy_job(body: DeployIn, request: Request):
    from databricks.sdk.service import jobs

    rows = run_sql(
        f"SELECT name FROM {settings.table('vsu_configs')} "
        f"WHERE config_id = {sql_str(body.config_id)}"
    )
    if not rows:
        raise HTTPException(404, "config not found")
    cfg_name = rows[0]["name"]
    safe = re.sub(r"[^a-zA-Z0-9_]+", "_", cfg_name).strip("_").lower() or "config"

    # Otherwise the job is owned only by the app's service principal, so non-admin users can't
    # see it. Grant ALL workspace users (the built-in `users` group) CAN_VIEW so anyone can see
    # the job + its runs; also give the person who clicked Deploy CAN_MANAGE so they can re-run.
    acl = [jobs.JobAccessControlRequest(
               group_name="users", permission_level=jobs.JobPermissionLevel.CAN_VIEW)]
    user = _requesting_user(request)
    if user:
        acl.append(jobs.JobAccessControlRequest(
            user_name=user, permission_level=jobs.JobPermissionLevel.CAN_MANAGE))

    w = get_workspace_client()
    job = w.jobs.create(
        name=f"vsu_upsell_{safe}",
        access_control_list=acl,
        tasks=[
            jobs.Task(
                task_key="run_upsell",
                notebook_task=jobs.NotebookTask(
                    notebook_path=_notebook_path("run_upsell_config"),
                    base_parameters={
                        "catalog": settings.catalog,
                        "schema": settings.schema,
                        "config_id": body.config_id,
                        "output_prefix": safe,
                    },
                ),
            )
        ],
    )
    job_id = job.job_id
    host = get_workspace_host()
    result = {"job_id": job_id, "job_url": f"{host}/jobs/{job_id}"}
    if body.run_now:
        run = w.jobs.run_now(job_id=job_id)
        result["run_id"] = run.run_id
        result["run_url"] = f"{host}/jobs/{job_id}/runs/{run.run_id}"
    return result
