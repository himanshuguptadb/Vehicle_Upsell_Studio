#!/usr/bin/env bash
# One-script deploy for Vehicle Service Upsell Studio.
# Builds the frontend, creates/updates the Databricks App, sets up the Unity Catalog
# schema + tables + component seed, uploads the job notebooks, grants the app's service
# principal the privileges it needs, generates sample data, syncs code, and deploys.
# Idempotent — safe to re-run.
set -euo pipefail

# --profile, --catalog and --warehouse-id are REQUIRED (no silent defaults) so the target
# workspace, catalog and warehouse are always an explicit choice. Each may be supplied via its
# VSU_<OPTION> env var instead; the CLI flag wins. The rest have defaults.
PROFILE="${VSU_PROFILE:-}"               # Databricks CLI profile = which workspace (required)
CATALOG="${VSU_CATALOG:-}"               # Unity Catalog to own the app's tables (required)
WAREHOUSE_ID="${VSU_WAREHOUSE_ID:-}"     # SQL Warehouse id (required)
SCHEMA="${VSU_SCHEMA:-vehicle_upsell}"   # Schema within the catalog
APP_NAME="${VSU_APP_NAME:-vehicle-upsell-studio}"
MODEL="${VSU_MODEL:-databricks-claude-sonnet-4-6}"  # default model shown in the app
ROWS="${VSU_ROWS:-150}"                  # sample-data customer count
GEN_SAMPLE="--generate-sample"

usage() {
  cat <<'EOF'
Vehicle Service Upsell Studio — deploy

Usage: ./deploy.sh --profile NAME --catalog NAME --warehouse-id ID [options]

Required:
  --profile NAME        Databricks CLI profile (the target workspace).
  --catalog NAME        Unity Catalog for the app's tables (must already exist).
  --warehouse-id ID     SQL Warehouse to run queries / ai_query.

Options:
  --schema NAME         Schema within the catalog.                          [vehicle_upsell]
  --app-name NAME       Databricks App name.                                [vehicle-upsell-studio]
  --model NAME          Default serving endpoint shown in the app.          [databricks-claude-sonnet-4-6]
  --rows N              Sample-data customer count.                         [150]
  --no-sample           Skip (re)generating sample data.
  -h, --help            Show this help.

Each option also has a VSU_<OPTION> env var (e.g. VSU_PROFILE, VSU_CATALOG, VSU_WAREHOUSE_ID).

Examples:
  ./deploy.sh --profile my-ws --catalog main --warehouse-id <warehouse-id>
  ./deploy.sh --profile my-ws --catalog sandbox --warehouse-id <warehouse-id> --rows 300 --schema upsell
  ./deploy.sh --profile my-ws --catalog main --warehouse-id <warehouse-id> --no-sample   # code only

Tip: list SQL warehouses to find an id:  databricks warehouses list -p <profile>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2;;
    --catalog) CATALOG="$2"; shift 2;;
    --schema) SCHEMA="$2"; shift 2;;
    --warehouse-id) WAREHOUSE_ID="$2"; shift 2;;
    --app-name) APP_NAME="$2"; shift 2;;
    --model) MODEL="$2"; shift 2;;
    --rows) ROWS="$2"; shift 2;;
    --no-sample) GEN_SAMPLE=""; shift;;
    -h|--help) usage; exit 0;;
    *) echo "unknown arg: $1"; echo; usage; exit 1;;
  esac
done

# Required args — fail fast with usage if any is missing.
missing=()
[[ -z "$PROFILE" ]] && missing+=("--profile")
[[ -z "$CATALOG" ]] && missing+=("--catalog")
[[ -z "$WAREHOUSE_ID" ]] && missing+=("--warehouse-id")
if (( ${#missing[@]} )); then
  echo "Missing required argument(s): ${missing[*]}"; echo
  usage
  echo
  echo "Tip: list SQL warehouses to find an id:  databricks warehouses list -p ${PROFILE:-<profile>}"
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
DB() { databricks "$@" -p "$PROFILE"; }

echo "==> Profile: $PROFILE  Catalog: $CATALOG.$SCHEMA  Warehouse: $WAREHOUSE_ID  App: $APP_NAME"

# 1. Build the frontend --------------------------------------------------------
echo "==> Building frontend..."
( cd frontend && npm ci && npm run build )
[[ -f frontend/dist/index.html ]] || { echo "frontend build failed"; exit 1; }

# 2. Create the app (idempotent) and read its service principal ----------------
echo "==> Ensuring app exists..."
DB apps create "$APP_NAME" --description "Vehicle Service Upsell Studio" 2>/dev/null || true

# Wait for the SP client id to be assigned.
APP_CLIENT_ID=""
for _ in $(seq 1 20); do
  APP_CLIENT_ID="$(DB apps get "$APP_NAME" -o json 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("service_principal_client_id") or "")' || true)"
  [[ -n "$APP_CLIENT_ID" ]] && break
  sleep 3
done
echo "==> App service principal: ${APP_CLIENT_ID:-<unknown>}"

# 3. Workspace setup: schema, tables, seed, notebooks, app.yaml, grants, sample
echo "==> Running workspace setup..."
python3 scripts/setup_workspace.py \
  --profile "$PROFILE" --catalog "$CATALOG" --schema "$SCHEMA" \
  --warehouse-id "$WAREHOUSE_ID" --model "$MODEL" --app-name "$APP_NAME" \
  --app-client-id "$APP_CLIENT_ID" --rows "$ROWS" $GEN_SAMPLE

# 4. Sync code to the workspace ------------------------------------------------
ME="$(DB current-user me -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)["userName"])')"
APP_WS_DIR="/Workspace/Users/$ME/$APP_NAME"
echo "==> Syncing code to $APP_WS_DIR..."
DB sync . "$APP_WS_DIR" \
  --exclude node_modules --exclude .venv --exclude __pycache__ \
  --exclude ".git" --exclude "frontend/src" --exclude "frontend/node_modules" \
  --exclude "jobs" --exclude "scripts" --full

# 5. Deploy --------------------------------------------------------------------
echo "==> Deploying app..."
DB apps deploy "$APP_NAME" --source-code-path "$APP_WS_DIR"

# 6. Summary -------------------------------------------------------------------
APP_URL="$(DB apps get "$APP_NAME" -o json | python3 -c 'import json,sys; print(json.load(sys.stdin).get("url",""))')"
echo ""
echo "============================================================"
echo " Deployed: $APP_NAME"
echo " URL:      $APP_URL"
echo " Logs:     ${APP_URL%/}/logz"
echo " Data:     $CATALOG.$SCHEMA"
echo "============================================================"
