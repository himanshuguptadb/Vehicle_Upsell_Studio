# Install & Deploy — Vehicle Service Upsell Studio

One command deploys the whole thing (frontend build, Databricks App, Unity Catalog schema +
tables + seed, job notebooks, service-principal grants, sample data, code sync, app deploy).
See [README.md](README.md) for what the app does and how to use it.

## Prerequisites

- **Databricks CLI** ≥ 0.229 — `brew install databricks` (or upgrade).
- **Node.js** ≥ 18 and **npm** (to build the frontend).
- **Python** ≥ 3.11 with the **databricks-sdk** (`pip install databricks-sdk`) for the setup script.
- A workspace with **Databricks Apps**, **Serverless SQL**, and **Foundation Model / serving
  endpoints** enabled, where you can create apps and jobs.
- An authenticated CLI profile for that workspace:
  ```bash
  databricks auth login --host https://<your-workspace-host> --profile <profile-name>
  ```
- The target **Unity Catalog must already exist** (the deploy creates the schema, not the catalog).

## Quick start

From the project directory, run the deploy. **`--profile`, `--catalog`, and `--warehouse-id`
are required** (so the target workspace, catalog, and warehouse are always an explicit choice):

```bash
./deploy.sh --profile <profile> --catalog <catalog> --warehouse-id <id>
```

Find a warehouse id with: `databricks warehouses list -p <profile>`.

Examples:

```bash
# Standard deploy (schema "vehicle_upsell", 150 sample customers)
./deploy.sh --profile my-workspace --catalog main --warehouse-id <warehouse-id>

# Custom schema and larger sample
./deploy.sh --profile my-workspace --catalog sandbox --warehouse-id <warehouse-id> \
            --schema upsell --rows 300

# Redeploy code only (don't regenerate sample data)
./deploy.sh --profile my-workspace --catalog main --warehouse-id <warehouse-id> --no-sample
```

When it finishes it prints the app URL. Open it (workspace SSO login required) and use the tabs
as described in the [README](README.md#using-the-app).

## Options

**Required** (or set the matching `VSU_*` env var):

| Flag | Env var | Meaning |
|---|---|---|
| `--profile` | `VSU_PROFILE` | Databricks CLI profile = **which workspace** |
| `--catalog` | `VSU_CATALOG` | Unity Catalog that owns the app's tables (must already exist) |
| `--warehouse-id` | `VSU_WAREHOUSE_ID` | **SQL Warehouse** for queries + `ai_query` |

**Optional:**

| Flag | Env var | Default | Meaning |
|---|---|---|---|
| `--schema` | `VSU_SCHEMA` | `vehicle_upsell` | Schema within the catalog |
| `--app-name` | `VSU_APP_NAME` | `vehicle-upsell-studio` | Databricks App name |
| `--model` | `VSU_MODEL` | `databricks-claude-sonnet-4-6` | default model shown in the app |
| `--rows` | `VSU_ROWS` | `150` | sample-data customer count |
| `--no-sample` | — | — | skip (re)generating sample data |

`./deploy.sh --help` prints this list. The script fails fast with usage if a required argument is
missing.

The deploy is **idempotent** — re-running rebuilds the frontend, re-syncs code, redeploys, and
re-applies grants. Catalog/schema/warehouse are also editable at runtime on the app's **Settings**
tab.

## What the deploy does

1. Builds the frontend (`npm ci && npm run build`).
2. Creates the Databricks App (if needed) and reads its service-principal id.
3. Runs `scripts/setup_workspace.py`: creates the schema + Delta tables, seeds the component
   catalog, uploads the two job notebooks, **grants the app's service principal** the privileges
   it needs (see below), renders `app.yaml`, and submits the sample-data job.
4. Syncs the code to the workspace and deploys the app.
5. Prints the app URL.

## App service-principal permissions

The app runs as its own service principal (SP). The deploy grants everything the SP needs, so no
manual permission setup is required:

| Privilege | On | Why |
|---|---|---|
| `USE CATALOG` | the catalog | reach the schema |
| `ALL PRIVILEGES` | the schema | create/read/write the app's Delta tables + read sample data |
| `CAN USE` | the SQL Warehouse | run Statement Execution + `ai_query` |
| `CAN MANAGE` | the jobs directory | run the sample-data + deploy job notebooks |
| `CAN QUERY` | any **custom** serving endpoint | use it for `ai_query` / prompt-assist |

Built-in foundation-model endpoints (`databricks-*`) have no per-endpoint ACL — they're governed
at the workspace/account level and are available to the SP by default, so nothing is granted for
them. Re-running `./deploy.sh` re-applies all grants.

## Local development

```bash
# backend (uses your CLI profile)
export DATABRICKS_PROFILE=<profile> CATALOG=<catalog> SCHEMA=vehicle_upsell WAREHOUSE_ID=<id>
pip install -r requirements.txt
uvicorn app:app --reload --port 8000

# frontend (proxies /api → :8000)
cd frontend && npm install && npm run dev   # http://localhost:5173
```

## Troubleshooting

- **App logs:** append `/logz` to the app URL.
- **`TABLE_OR_VIEW_NOT_FOUND` on a run:** sample data hasn't been generated for that
  catalog/schema — run **Settings → Generate sample data**, or `./deploy.sh … ` (without
  `--no-sample`).
- **Permission errors from the app:** re-run `./deploy.sh` so the app service principal gets the
  UC + warehouse + serving grants.
- **Slow `ai_query`:** every row is one LLM call — keep test-run row counts modest; full-scale
  jobs over thousands of rows take time.
- **`ai_query` response-format errors:** the app uses the **JSON-schema** `responseFormat` form
  (the DDL-string form rejects arrays / multi-field outputs).
