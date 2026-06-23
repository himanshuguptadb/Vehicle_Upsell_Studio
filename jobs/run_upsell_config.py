# Databricks notebook source
# MAGIC %md
# MAGIC # Run a saved upsell prompt-config at full scale
# MAGIC Reads a prompt-config from `vsu_configs` (by `config_id`), runs its `ai_query`
# MAGIC classification over the **entire** `service` table, writes a per-component
# MAGIC recommendations table, and drafts follow-up emails for customers with any
# MAGIC **Urgent** finding.
# MAGIC
# MAGIC Fixes vs. the original accelerator: correct `service -> vehicle -> customer`
# MAGIC join (was `service_id = customer_id`), and the email uses the *reasoning* text.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "vehicle_upsell")
dbutils.widgets.text("config_id", "")
dbutils.widgets.text("output_prefix", "config")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
config_id = dbutils.widgets.get("config_id")
prefix = dbutils.widgets.get("output_prefix")

spark.sql(f"USE CATALOG `{catalog}`")
spark.sql(f"USE SCHEMA `{schema}`")

assert config_id, "config_id widget is required"

# COMMAND ----------

import json

row = spark.sql(
    "SELECT name, model_endpoint, prompt_text, components FROM vsu_configs "
    "WHERE config_id = :cid", args={"cid": config_id}
).collect()
assert row, f"config {config_id} not found"
cfg = row[0]
model = cfg["model_endpoint"]
prompt_text = cfg["prompt_text"]
components = json.loads(cfg["components"] or "[]")
keys = [c["component_key"] for c in components]
print(f"Config '{cfg['name']}' | model={model} | components={keys}")

CLASSES = ["Urgent", "Upcoming", "Good"]
contract = (
    f"\n\nReturn an assessment for EACH of these component keys exactly: [{', '.join(keys)}]. "
    f"Use the component key verbatim in the 'component' field. "
    f"'classification' must be one of {CLASSES}."
)
full_prompt = prompt_text + contract

import json
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
PARSE_SCHEMA = ("STRUCT<assessments: ARRAY<STRUCT<"
                "component: STRING, classification: STRING, reasoning: STRING>>>")

# COMMAND ----------

from pyspark.sql.functions import expr, col, explode, from_json, array_contains, coalesce, array

prompt_lit = full_prompt.replace("\\", "\\\\").replace("'", "\\'")
schema_lit = RESPONSE_JSON_SCHEMA.replace("\\", "\\\\").replace("'", "\\'")

# Repartition before ai_query so per-row endpoint calls fan out across tasks instead of
# running near-serially within a few large partitions. 32 is a moderate concurrency level
# that speeds up throughput without overwhelming the (rate-limited) pay-per-token endpoint;
# raise it for very large tables on a bigger warehouse.
scored = spark.table("service").repartition(32).withColumn(
    "result",
    from_json(
        expr(
            f"ai_query('{model}', "
            f"concat('{prompt_lit}', '\\n\\nService notes:\\n', service_performed), "
            f"responseFormat => '{schema_lit}', "
            f"modelParameters => named_struct('temperature', 0, 'max_tokens', 256))"
        ),
        PARSE_SCHEMA,
    ),
).withColumn("flagged_components", coalesce(col("flagged_components"), array()))

recommendations = (
    scored
    .select("service_id", "vehicle_id", "service_performed", "flagged_components",
            explode("result.assessments").alias("a"))
    .select(
        "service_id", "vehicle_id", "service_performed",
        col("a.component").alias("component_key"),
        col("a.classification").alias("classification"),
        col("a.reasoning").alias("reasoning"),
        array_contains(col("flagged_components"), col("a.component")).alias("technician_flagged"),
    )
)

rec_table = f"{prefix}_recommendations"
recommendations.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable(rec_table)
# Count the WRITTEN table, not the `recommendations` DataFrame: the latter is lazy and its
# lineage contains the ai_query, so counting it would re-run every LLM call a second time over
# the full table. Reading the materialized Delta table is a cheap metadata/scan.
n_rec = spark.table(rec_table).count()
print(f"Wrote {n_rec} component recommendations to {catalog}.{schema}.{rec_table}")

# COMMAND ----------

# MAGIC %md
# MAGIC ## Draft follow-up emails for customers with any Urgent finding

# COMMAND ----------

spark.sql(f"""
CREATE OR REPLACE TABLE {prefix}_emails AS
WITH urgent AS (
  SELECT service_id, vehicle_id,
         concat_ws('; ', collect_list(concat(component_key, ': ', reasoning))) AS urgent_reasons
  FROM {rec_table}
  WHERE classification = 'Urgent'
  GROUP BY service_id, vehicle_id
)
SELECT
  u.service_id,
  u.vehicle_id,
  c.customer_id,
  c.first_name,
  c.last_name,
  c.email,
  v.make,
  v.model,
  u.urgent_reasons,
  ai_query(
    '{model}',
    concat(
      'You are an automotive service communication assistant. Write a personalized, empathetic, ',
      'professional follow-up email to a customer who recently serviced their vehicle. The technician ',
      'found issues that need attention soon for safety. Acknowledge their visit, restate the issue in ',
      'plain language, explain the safety relevance without alarm, and offer to schedule the work. ',
      'Customer: ', c.first_name, ' ', c.last_name,
      '. Vehicle: ', v.make, ' ', v.model,
      '. Findings needing attention: ', u.urgent_reasons,
      '. Keep it concise, warm, and trust-building.'
    ),
    modelParameters => named_struct('temperature', 0.3, 'max_tokens', 1024)
  ) AS custom_email
FROM urgent u
JOIN vehicle v ON u.vehicle_id = v.vehicle_id
JOIN customer c ON v.customer_id = c.customer_id
""")

n = spark.table(f"{prefix}_emails").count()
print(f"Wrote {n} follow-up emails to {catalog}.{schema}.{prefix}_emails")
