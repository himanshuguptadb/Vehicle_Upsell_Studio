# Vehicle Service Upsell Studio

A self-service **Databricks App** for building, testing, comparing, and deploying
`ai_query`-based **vehicle service upsell** analysis — the interactive evolution of the
[`vehicle_service_upsell`](https://github.com/databricks-industry-solutions/vehicle_service_upsell)
solution accelerator.

Service centers capture rich technical detail at every visit (tread depth, brake-pad mm,
battery voltage, fluid condition…) but those readings are often logged and forgotten. This
app lets a non-engineer **point any LLM at those notes, with a prompt they design, to surface
upsell/maintenance opportunities the technician didn't flag** — and prove the value before
running it at scale.

> **Install & deploy instructions: see [INSTALL.md](INSTALL.md)** (one command: `./deploy.sh`).

## What you can do

1. **Pick any chat LLM** you have access to (any `llm/v1/chat` serving endpoint).
2. **Choose the vehicle component** to analyze (seeded, editable catalog).
3. **Author a prompt** — generate a first draft with the LLM, then refine it with the LLM
   ("Improve") or edit it by hand. Start fresh or refine a saved config.
4. **Test** the prompt with `ai_query` on sample data and read the per-row results next to the
   **technician's raw notes** — including a **⚠ AI catch** column showing opportunities the
   technician did *not* flag.
5. **Save** configs (every save is a new, immutable version — nothing is overwritten) and
   **compare two** side by side: prompts, per-row classifications, disagreements, and
   distributions.
6. **Deploy** a chosen config as a **Lakeflow Job** that runs over the full service table and
   drafts personalized follow-up emails for customers with urgent findings.

## Architecture

```
┌─ Databricks App (service principal) ─────────────────────────────┐
│  FastAPI (app.py, server/)                                       │
│   • config/component CRUD + ai_query test/compare runs           │──▶ SQL Warehouse
│     via the SQL Statement Execution API                          │    (Statement Execution
│   • prompt-assist via serving-endpoint chat completions          │     runs ai_query too)
│   • serves the prebuilt React SPA (frontend/dist)                │──▶ Serving endpoints (LLMs)
│  React + Vite + Tailwind (frontend/)                             │
└──────────────────────────────────────────────────────────────────┘
        creates / runs                  reads / writes
            ▼                                 ▼
   Lakeflow Jobs (jobs/)            Delta tables in {catalog}.{schema}
   • generate_sample_data           vsu_components / vsu_configs /
   • run_upsell_config              vsu_runs / vsu_run_results /
                                    customer / vehicle / technician / service
```

- **Storage:** all state is **Delta tables** in `{catalog}.{schema}` (no Lakebase/Postgres),
  reached through the **SQL Statement Execution API**.
- **Auth:** dual-mode — the app's **service principal** in the workspace, your CLI profile
  locally.
- **Sample data is deterministic** (templated raw measurements, no LLM), so prompts/thresholds
  visibly drive the classification and the "AI catch" misses are exact per component.

## Repository layout

```
vehicle_upsell_studio/
├── deploy.sh                     # one-command, parameterized deploy
├── INSTALL.md                    # install & deploy instructions
├── app.yaml                      # Databricks App config (rendered by the deploy)
├── requirements.txt / pyproject.toml
├── app.py                        # FastAPI entrypoint (API + serves frontend/dist)
├── server/                       # backend
│   ├── config.py                 # dual-mode auth + runtime settings
│   ├── sql.py                    # Statement Execution helpers
│   ├── llm.py                    # serving-endpoint chat client + model list
│   ├── aiquery.py                # compose ai_query SQL + parse/explode + flags
│   ├── bootstrap_sql.py          # DDL + component seed
│   └── routes/                   # models, components, configs, prompt, runs, sample, deploy, settings
├── jobs/                         # notebooks run as Lakeflow Jobs
│   ├── generate_sample_data.py   # synthetic data (deterministic measurement notes)
│   └── run_upsell_config.py      # full-scale config run + follow-up emails
├── scripts/setup_workspace.py    # schema/tables/seed, notebook upload, grants, app.yaml render
└── frontend/                     # React + Vite + Tailwind SPA
```

## Install

One command — see **[INSTALL.md](INSTALL.md)** for prerequisites, options, and details:

```bash
./deploy.sh --profile <profile> --catalog <catalog> --warehouse-id <id>
```

`--profile`, `--catalog`, and `--warehouse-id` are required (so the target workspace, catalog,
and warehouse are always explicit); `--schema`, `--app-name`, `--model`, and `--rows` are
optional. The deploy is idempotent. `./deploy.sh --help` lists every option.

## Using the app

Open the printed URL (workspace SSO login required). Tabs:

1. **Components** — select the component to analyze (single-select for the demo); add/edit/remove
   components and their rubrics.
2. **Prompt Builder** — *Start from* (scratch or refine a saved config) → *Component & model* →
   *Prompt* (Generate / Improve) → *Test on sample data* → *Save as new config*.
3. **Saved Configs** — list / open (to refine) / delete saved versions.
4. **Compare** — pick two configs, run both on the same sample, and view their prompts,
   distributions, and a row-level diff (with technician notes).
5. **Deploy** — turn a saved config into a Lakeflow Job and run it.
6. **Settings** — change target catalog/schema/warehouse/model and regenerate sample data.

## Sample data

The deploy seeds synthetic `customer` / `vehicle` / `technician` / `service` data. **Service
notes are raw measurements** (e.g. *"Tread depth (32nds): LF 2, RF 3… Battery: 11.6V, age 5 yr."*)
with **no verdicts**, so the prompt is what produces the classification. Each service records
`flagged_components` — the single most-severe component the technician flagged — so the app can
show which opportunities the AI surfaced that the technician missed.

Regenerate anytime from **Settings → Generate sample data**, or `./deploy.sh … --rows N`.

## Data model (`{catalog}.{schema}`)

| Table | Purpose |
|---|---|
| `vsu_components` | component catalog (key, name, description, rubric, enabled) |
| `vsu_configs` | saved prompt configs (immutable versions) |
| `vsu_runs`, `vsu_run_results` | persisted test-run history |
| `customer`, `vehicle`, `technician`, `service` | sample data (`service` has `flagged_components`, `ground_truth`) |
| `<config>_recommendations`, `<config>_emails` | outputs written by a deployed job |

## Credits

Built on the Databricks `vehicle_service_upsell` solution accelerator. Uses Faker (MIT) for
synthetic data.
