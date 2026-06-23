#!/usr/bin/env python3
"""Idempotent workspace setup for Vehicle Service Upsell Studio.

Run by deploy.sh (or standalone). Creates the UC schema + Delta tables, seeds the
component catalog, uploads the job notebooks, renders app.yaml with the resolved
target, optionally grants the app's service principal the privileges it needs, and
optionally submits the sample-data generation job.

Reuses the backend's own DDL/seed helpers so there is one source of truth.
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
import time

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default="")
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--schema", required=True)
    ap.add_argument("--warehouse-id", required=True)
    ap.add_argument("--model", default="databricks-claude-sonnet-4-6")
    ap.add_argument("--app-name", required=True)
    ap.add_argument("--app-client-id", default="", help="App service principal id for grants")
    ap.add_argument("--rows", type=int, default=300)
    ap.add_argument("--generate-sample", action="store_true")
    ap.add_argument("--wait-sample", action="store_true")
    args = ap.parse_args()

    # Seed env BEFORE importing server modules (settings reads env at import).
    if args.profile:
        os.environ["DATABRICKS_PROFILE"] = args.profile
    os.environ["CATALOG"] = args.catalog
    os.environ["SCHEMA"] = args.schema
    os.environ["WAREHOUSE_ID"] = args.warehouse_id
    os.environ["DEFAULT_MODEL"] = args.model
    os.environ.pop("DATABRICKS_APP_NAME", None)  # ensure local auth mode

    from databricks.sdk.service import jobs
    from databricks.sdk.service.workspace import ImportFormat, Language

    from server.bootstrap_sql import ddl_statements, seed_components_sql
    from server.config import get_workspace_client, get_workspace_host, settings
    from server.sql import run_sql

    w = get_workspace_client()
    me = w.current_user.me().user_name
    jobs_dir = f"/Workspace/Users/{me}/{args.app_name}_jobs"
    print(f"[setup] user={me}  target={args.catalog}.{args.schema}  jobs_dir={jobs_dir}")

    # 1. Schema + tables + component seed --------------------------------------
    print("[setup] creating schema + tables…")
    run_sql(f"CREATE SCHEMA IF NOT EXISTS {settings.fq_schema}")
    for tmpl in ddl_statements():
        run_sql(tmpl.format(
            components=settings.table("vsu_components"),
            configs=settings.table("vsu_configs"),
            runs=settings.table("vsu_runs"),
            run_results=settings.table("vsu_run_results"),
        ))
    run_sql(seed_components_sql(settings.table("vsu_components")))
    print("[setup] seeded components.")

    # 2. Upload job notebooks --------------------------------------------------
    w.workspace.mkdirs(jobs_dir)
    for nb in ("generate_sample_data", "run_upsell_config"):
        local = os.path.join(REPO, "jobs", f"{nb}.py")
        with open(local, "rb") as fh:
            content = base64.b64encode(fh.read()).decode()
        w.workspace.import_(
            path=f"{jobs_dir}/{nb}",
            format=ImportFormat.SOURCE,
            language=Language.PYTHON,
            content=content,
            overwrite=True,
        )
        print(f"[setup] uploaded notebook {jobs_dir}/{nb}")

    # 3. Render app.yaml with the resolved target ------------------------------
    render_app_yaml(REPO, args, jobs_dir)
    print("[setup] wrote app.yaml")

    # 4. Grant the app service principal the privileges it needs ---------------
    if args.app_client_id:
        grant_app_sp(w, run_sql, args, jobs_dir)

    # 5. Optionally generate sample data ---------------------------------------
    if args.generate_sample:
        print(f"[setup] submitting sample-data job ({args.rows} customers)…")
        run = w.jobs.submit(
            run_name="vsu_generate_sample_data",
            tasks=[jobs.SubmitTask(
                task_key="generate",
                notebook_task=jobs.NotebookTask(
                    notebook_path=f"{jobs_dir}/generate_sample_data",
                    base_parameters={"catalog": args.catalog, "schema": args.schema,
                                     "rows": str(args.rows), "model": args.model},
                ),
            )],
        )
        print(f"[setup] sample job run: {get_workspace_host()}/jobs/runs/{run.run_id}")
        if args.wait_sample:
            wait_run(w, run.run_id)

    print("[setup] done.")


def render_app_yaml(repo: str, args, jobs_dir: str) -> None:
    path = os.path.join(repo, "app.yaml")
    content = f"""command:
  - "uvicorn"
  - "app:app"
  - "--host"
  - "0.0.0.0"
  - "--port"
  - "8000"

env:
  - name: CATALOG
    value: "{args.catalog}"
  - name: SCHEMA
    value: "{args.schema}"
  - name: WAREHOUSE_ID
    value: "{args.warehouse_id}"
  - name: DEFAULT_MODEL
    value: "{args.model}"
  - name: JOBS_WORKSPACE_DIR
    value: "{jobs_dir}"
"""
    with open(path, "w") as fh:
        fh.write(content)


def grant_app_sp(w, run_sql, args, jobs_dir: str) -> None:
    sp = args.app_client_id
    print(f"[setup] granting privileges to app SP {sp}…")
    # Unity Catalog privileges
    try:
        run_sql(f"GRANT USE CATALOG ON CATALOG `{args.catalog}` TO `{sp}`")
        run_sql(f"GRANT ALL PRIVILEGES ON SCHEMA `{args.catalog}`.`{args.schema}` TO `{sp}`")
        print("[setup]   UC grants ok")
    except Exception as e:  # noqa: BLE001
        print(f"[setup]   WARN UC grant failed: {e}")
    # SQL Warehouse CAN_USE
    try:
        from databricks.sdk.service.sql import WarehouseAccessControlRequest, WarehousePermissionLevel
        w.warehouses.update_permissions(
            warehouse_id=args.warehouse_id,
            access_control_list=[WarehouseAccessControlRequest(
                service_principal_name=sp, permission_level=WarehousePermissionLevel.CAN_USE)],
        )
        print("[setup]   warehouse CAN_USE ok")
    except Exception as e:  # noqa: BLE001
        print(f"[setup]   WARN warehouse grant failed: {e}")
    # Jobs notebook directory — let the SP read/run the uploaded notebooks
    try:
        from databricks.sdk.service.workspace import (
            WorkspaceObjectAccessControlRequest, WorkspaceObjectPermissionLevel)
        obj = w.workspace.get_status(jobs_dir)
        w.workspace.update_permissions(
            workspace_object_type="directories",
            workspace_object_id=str(obj.object_id),
            access_control_list=[WorkspaceObjectAccessControlRequest(
                service_principal_name=sp,
                permission_level=WorkspaceObjectPermissionLevel.CAN_MANAGE)],
        )
        print("[setup]   jobs dir ACL ok")
    except Exception as e:  # noqa: BLE001
        print(f"[setup]   WARN jobs dir ACL failed: {e}")
    # Serving endpoints — built-in foundation-model endpoints (databricks-*) have no
    # per-endpoint ACL (id is None) and are open at the workspace level, so nothing to do
    # there. For any CUSTOM serving endpoint (has an id), grant the SP CAN_QUERY so the app
    # can use it for ai_query / prompt-assist.
    try:
        from databricks.sdk.service.serving import (
            ServingEndpointAccessControlRequest, ServingEndpointPermissionLevel)
        granted = 0
        for ep in w.serving_endpoints.list():
            if not getattr(ep, "id", None):
                continue  # built-in FM endpoint — workspace-governed, no ACL
            try:
                w.serving_endpoints.update_permissions(
                    serving_endpoint_id=ep.id,
                    access_control_list=[ServingEndpointAccessControlRequest(
                        service_principal_name=sp,
                        permission_level=ServingEndpointPermissionLevel.CAN_QUERY)],
                )
                granted += 1
            except Exception:  # noqa: BLE001
                pass
        print(f"[setup]   serving endpoint CAN_QUERY granted on {granted} custom endpoint(s)")
    except Exception as e:  # noqa: BLE001
        print(f"[setup]   WARN serving endpoint grant skipped: {e}")


def wait_run(w, run_id: int, timeout: int = 1800) -> None:
    waited = 0
    while waited < timeout:
        r = w.jobs.get_run(run_id=run_id)
        life = r.state.life_cycle_state.value if r.state and r.state.life_cycle_state else None
        if life in ("TERMINATED", "INTERNAL_ERROR", "SKIPPED"):
            res = r.state.result_state.value if r.state and r.state.result_state else None
            print(f"[setup] sample job finished: {life} / {res}")
            return
        time.sleep(15)
        waited += 15
    print("[setup] WARN sample job wait timed out")


if __name__ == "__main__":
    main()
