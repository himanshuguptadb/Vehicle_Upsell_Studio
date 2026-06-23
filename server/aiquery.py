"""Compose the ai_query SQL for a prompt-config and parse the structured results.

A config classifies upsell opportunity for a set of vehicle components from a
technician's free-text service notes. We make ONE ai_query call per service row that
returns an array of per-component assessments — efficient and gives a clean diff when
comparing two configs.
"""
from __future__ import annotations

import json

from .config import settings
from .sql import run_sql, sql_str

CLASSES = ["Urgent", "Upcoming", "Good"]

# ai_query's DDL-string responseFormat rejects a top-level ARRAY field, so we use the
# JSON-schema form (which supports arrays + enums). The call returns a JSON STRING that
# we parse back with from_json using PARSE_SCHEMA.
RESPONSE_JSON_SCHEMA = json.dumps({
    "type": "json_schema",
    "json_schema": {
        "name": "vsu_assessments",
        "schema": {
            "type": "object",
            "properties": {
                "assessments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "component": {"type": "string"},
                            "classification": {"type": "string", "enum": CLASSES},
                            "reasoning": {"type": "string"},
                        },
                        "required": ["component", "classification", "reasoning"],
                    },
                }
            },
            "required": ["assessments"],
        },
        "strict": True,
    },
})

PARSE_SCHEMA = (
    "STRUCT<assessments: ARRAY<STRUCT<"
    "component: STRING, classification: STRING, reasoning: STRING>>>"
)

# Pin inference for speed + determinism: temperature 0 avoids sampling overhead and makes
# runs/compares reproducible; a tight max_tokens cap stops the model from over-generating.
# This is the main performance lever — without it ai_query is markedly slower per row.
# 256 is ample for one short per-component reasoning; bump it if you enable multi-component configs.
MODEL_PARAMETERS = "named_struct('temperature', 0, 'max_tokens', 256)"

# Kept for the configs table's response_format column (record of the output contract).
RESPONSE_FORMAT = RESPONSE_JSON_SCHEMA


def default_prompt(components: list[dict]) -> str:
    """A sensible starting prompt the user can immediately tweak or AI-regenerate."""
    lines = [
        "You are an expert automotive service advisor. Read the technician's service "
        "notes and assess upsell/replacement opportunity for each of the components "
        "listed below.",
        "",
        "For EACH component, classify as exactly one of:",
        "- Urgent: replace immediately for safety or function.",
        "- Upcoming: replacement recommended at the next service interval.",
        "- Good: no action needed, or the notes contain no relevant signal.",
        "",
        "Components to assess:",
    ]
    for c in components:
        desc = c.get("description") or ""
        rubric = c.get("rubric") or ""
        line = f"- {c['display_name']} ({c['component_key']})"
        if desc:
            line += f": {desc}"
        lines.append(line)
        if rubric:
            lines.append(f"    Rubric: {rubric}")
    lines += [
        "",
        "Return one assessment per component with a concise reasoning grounded in the "
        "notes. If the notes say nothing about a component, classify it 'Good' with "
        "reasoning 'No relevant signal in notes.'",
    ]
    return "\n".join(lines)


def compose_full_prompt(prompt_text: str, components: list[dict]) -> str:
    """Append the explicit component-key contract so the model returns every key."""
    keys = ", ".join(c["component_key"] for c in components)
    contract = (
        f"\n\nReturn an assessment for EACH of these component keys exactly: [{keys}]. "
        f"Use the component key verbatim in the 'component' field. "
        f"'classification' must be one of {CLASSES}."
    )
    return prompt_text + contract


def build_run_sql(*, model: str, prompt_text: str, components: list[dict],
                  source_table: str, limit: int) -> str:
    """SQL that runs ai_query over the sample and explodes per-component results."""
    full_prompt = compose_full_prompt(prompt_text, components)
    src = settings.table(source_table)
    # `ORDER BY ... LIMIT n` collapses the sample to ONE partition, so the per-row ai_query
    # calls run with almost no parallelism. Repartitioning to ~one-row-per-partition lets the
    # warehouse issue concurrent endpoint requests (measured ~2x faster on a small warehouse;
    # gains are then bounded by the warehouse's core count). Capped to avoid pointless shuffle.
    parts = max(1, min(int(limit), 32))
    return f"""
WITH sample AS (
  SELECT service_id, service_type, service_performed,
         coalesce(flagged_components, array()) AS flagged_components
  FROM {src}
  ORDER BY service_id
  LIMIT {int(limit)}
),
scored AS (
  SELECT /*+ REPARTITION({parts}) */
    service_id,
    service_performed,
    flagged_components,
    from_json(
      ai_query(
        {sql_str(model)},
        concat({sql_str(full_prompt)}, '\\n\\nService notes:\\n', service_performed),
        responseFormat => {sql_str(RESPONSE_JSON_SCHEMA)},
        modelParameters => {MODEL_PARAMETERS}
      ),
      {sql_str(PARSE_SCHEMA)}
    ) AS result
  FROM sample
)
SELECT
  service_id,
  service_performed,
  a.component   AS component_key,
  a.classification AS classification,
  a.reasoning   AS reasoning,
  array_contains(flagged_components, a.component) AS technician_flagged
FROM scored
LATERAL VIEW explode(result.assessments) t AS a
ORDER BY service_id, component_key
""".strip()


def run_config(*, model: str, prompt_text: str, components: list[dict],
               source_table: str, limit: int) -> list[dict]:
    sql = build_run_sql(model=model, prompt_text=prompt_text, components=components,
                        source_table=source_table, limit=limit)
    return run_sql(sql)


def preview_prompt(prompt_text: str, components: list[dict]) -> str:
    return compose_full_prompt(prompt_text, components)


def distribution(rows: list[dict]) -> dict:
    """Counts by component_key x classification — used for the compare summary."""
    out: dict[str, dict[str, int]] = {}
    for r in rows:
        comp = r.get("component_key") or "?"
        cls = r.get("classification") or "?"
        out.setdefault(comp, {})
        out[comp][cls] = out[comp].get(cls, 0) + 1
    return out
