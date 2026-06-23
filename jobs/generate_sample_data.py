# Databricks notebook source
# MAGIC %md
# MAGIC # Generate synthetic vehicle-service sample data (deterministic)
# MAGIC Technician notes are **raw measurements/observations only — no verdicts** (no
# MAGIC "urgent"/"replace"/"good"). This is deliberate: the *prompt* is what turns the
# MAGIC readings into a classification, so changing the prompt visibly changes results, and
# MAGIC the AI can surface opportunities the technician logged but didn't flag.
# MAGIC
# MAGIC Each service stores `flagged_components` — the components the technician explicitly
# MAGIC called out (only the single most-severe one), so everything else the AI flags is a
# MAGIC genuine "miss". `ground_truth` stores the true per-component severity for reference.
# MAGIC No LLM is used, so this runs in seconds.

# COMMAND ----------

# MAGIC %pip install faker
# MAGIC %restart_python

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "vehicle_upsell")
dbutils.widgets.text("rows", "150")
dbutils.widgets.text("model", "")  # unused (kept for interface compatibility)

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")
n_customers = int(dbutils.widgets.get("rows"))

spark.sql(f"USE CATALOG `{catalog}`")
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{schema}`")
spark.sql(f"USE SCHEMA `{schema}`")

# COMMAND ----------

import json
import random
from faker import Faker

fake = Faker()

# -----------------------------------------------------------------------------
# Per-component measurement generators. Each returns (observation_text, severity).
# The text is FACTUAL ONLY — measurements/observations, never a verdict. Severity is
# the deterministic ground truth derived from the reading (used for flags + reference),
# NOT surfaced in the note text.
# -----------------------------------------------------------------------------
def g_tires():
    treads = [random.choice([2, 3, 3, 4, 5, 6, 7, 8, 9]) for _ in range(4)]
    mn = min(treads)
    sev = "Urgent" if mn < 3 else ("Upcoming" if mn <= 4 else "Good")
    return (f"Tread depth (32nds): LF {treads[0]}, RF {treads[1]}, "
            f"LR {treads[2]}, RR {treads[3]}."), sev

def g_brakes():
    front = random.choice([1.5, 2, 3, 3, 4, 5, 6, 7])
    rear = random.choice([2, 3, 4, 5, 6, 7, 8])
    mn = min(front, rear)
    sev = "Urgent" if mn < 2.5 else ("Upcoming" if mn <= 4 else "Good")
    return f"Brake pad thickness: front {front}mm, rear {rear}mm.", sev

def g_battery():
    v = round(random.uniform(11.4, 12.8), 1)
    age = random.randint(1, 7)
    sev = "Urgent" if (v < 11.8 or age >= 6) else ("Upcoming" if (v < 12.3 or age >= 4) else "Good")
    return f"Battery: {v}V resting, age {age} yr.", sev

def _choice(opts):
    return random.choice(opts)

def g_suspension():
    return _choice([
        ("Suspension: struts dry, no measurable play.", "Good"),
        ("Suspension: light strut weep, ~1mm ball-joint play.", "Upcoming"),
        ("Suspension: front strut leaking, ~3mm ball-joint play.", "Urgent"),
    ])

def g_engine_oil():
    return _choice([
        ("Engine oil: amber, level full.", "Good"),
        ("Engine oil: darkened, level mid, ~1k mi to interval.", "Upcoming"),
        ("Engine oil: black/thick, level 1qt low.", "Urgent"),
    ])

def g_coolant():
    return _choice([
        ("Coolant: level full, clean.", "Good"),
        ("Coolant: ~10% low, slight discoloration.", "Upcoming"),
        ("Coolant: below MIN, contaminated.", "Urgent"),
    ])

def g_transmission_fluid():
    return _choice([
        ("ATF: bright red, level full.", "Good"),
        ("ATF: light brown, level ok.", "Upcoming"),
        ("ATF: dark brown, burnt odor.", "Urgent"),
    ])

def g_belts_hoses():
    return _choice([
        ("Serpentine belt: no cracking; hoses firm.", "Good"),
        ("Serpentine belt: minor surface cracks; upper hose slightly soft.", "Upcoming"),
        ("Serpentine belt: frayed edge/glazing; lower hose seeping.", "Urgent"),
    ])

def g_lights_electrical():
    return _choice([
        ("Lights: all exterior functional.", "Good"),
        ("Lights: RH low-beam dim, license plate lamp out.", "Upcoming"),
        ("Lights: RH brake lamp inoperative.", "Urgent"),
    ])

def g_wipers():
    return _choice([
        ("Wipers: clean wipe, no chatter.", "Good"),
        ("Wipers: light streaking on driver side.", "Upcoming"),
        ("Wipers: torn driver blade, large unswept band.", "Urgent"),
    ])

def g_exhaust():
    return _choice([
        ("Exhaust: intact, no leaks, light surface rust.", "Good"),
        ("Exhaust: moderate corrosion at mid-pipe.", "Upcoming"),
        ("Exhaust: leak at flange, perforation starting.", "Urgent"),
    ])

def g_ac():
    t = random.choice([40, 44, 48, 55, 62, 70])
    sev = "Good" if t <= 48 else ("Upcoming" if t <= 60 else "Urgent")
    return f"A/C: vent temp {t}°F at max cool.", sev

GENERATORS = {
    "tires": g_tires, "brakes": g_brakes, "battery": g_battery, "suspension": g_suspension,
    "engine_oil": g_engine_oil, "coolant": g_coolant, "transmission_fluid": g_transmission_fluid,
    "belts_hoses": g_belts_hoses, "lights_electrical": g_lights_electrical, "wipers": g_wipers,
    "exhaust": g_exhaust, "ac": g_ac,
}
SERVICE_TYPES = ["Scheduled maintenance", "Multi-point inspection", "Oil change",
                 "Brake inspection", "Diagnostic check", "Tire rotation"]

# -----------------------------------------------------------------------------
# Curated demo rows. These occupy the LOWEST service_ids (1..N) so they appear first
# under the app's `ORDER BY service_id LIMIT n`, guaranteeing clear "AI catch" cases for
# TIRES and BRAKES within the first ~10 rows: Urgent readings present in the notes that the
# technician did NOT flag. A couple of Good rows and one tech-flagged row keep the
# distribution credible (so it's not "always a catch"). Readings are unambiguous vs the
# seeded rubric (tires Urgent < 3/32"; brakes Urgent pads < 2mm).
# Tuple: (service_performed, flagged_components, ground_truth)
DEMO_SERVICES = [
    ("Tread depth (32nds): LF 2, RF 2, LR 3, RR 3. Brake pad thickness: front 1.5mm, rear 2mm. "
     "Battery: 12.5V resting, age 2 yr.",
     [], {"tires": "Urgent", "brakes": "Urgent", "battery": "Good"}),
    ("Wipers: torn driver blade, large unswept band. Tread depth (32nds): LF 2, RF 3, LR 2, RR 4. "
     "Brake pad thickness: front 1.5mm, rear 3mm.",
     ["wipers"], {"wipers": "Urgent", "tires": "Urgent", "brakes": "Urgent"}),
    ("Tread depth (32nds): LF 1, RF 2, LR 2, RR 3. Brake pad thickness: front 1.5mm, rear 2mm. "
     "Engine oil: amber, level full.",
     [], {"tires": "Urgent", "brakes": "Urgent", "engine_oil": "Good"}),
    ("Tread depth (32nds): LF 8, RF 7, LR 8, RR 7. Brake pad thickness: front 7mm, rear 6mm. "
     "Coolant: level full, clean.",
     [], {"tires": "Good", "brakes": "Good", "coolant": "Good"}),
    ("Tread depth (32nds): LF 2, RF 3, LR 4, RR 4. Brake pad thickness: front 4mm, rear 3mm. "
     "Lights: all exterior functional.",
     ["tires"], {"tires": "Urgent", "brakes": "Upcoming", "lights_electrical": "Good"}),
    ("Tread depth (32nds): LF 4, RF 4, LR 5, RR 5. Brake pad thickness: front 1.5mm, rear 2mm. "
     "Lights: RH low-beam dim, license plate lamp out.",
     [], {"tires": "Upcoming", "brakes": "Urgent", "lights_electrical": "Upcoming"}),
    ("Tread depth (32nds): LF 2, RF 2, LR 2, RR 2. Brake pad thickness: front 1.5mm, rear 1.5mm.",
     [], {"tires": "Urgent", "brakes": "Urgent"}),
    ("Tread depth (32nds): LF 8, RF 8, LR 7, RR 8. Brake pad thickness: front 2mm, rear 1.5mm. "
     "Battery: 12.4V resting, age 3 yr.",
     [], {"tires": "Good", "brakes": "Urgent", "battery": "Good"}),
]

# COMMAND ----------

specializations = ["Engine", "Brakes", "Electrical", "Tires", "General Maintenance"]
technicians = [{
    "technician_id": i + 1, "first_name": fake.first_name(),
    "last_name": fake.last_name(), "specialization": random.choice(specializations),
} for i in range(10)]

model_types = ["Sedan", "SUV", "Coupe", "Hatchback", "Convertible", "Truck"]
customers, vehicles, services = [], [], []
vehicle_id_counter = 1
# Reserve the lowest ids for the curated demo rows so they sort first.
service_id_counter = len(DEMO_SERVICES) + 1
all_keys = list(GENERATORS.keys())

for customer_id in range(1, n_customers + 1):
    customers.append({
        "customer_id": customer_id, "first_name": fake.first_name(),
        "last_name": fake.last_name(), "email": fake.unique.email(),
        "phone": fake.phone_number(), "address": fake.address(),
    })
    for _ in range(random.randint(1, 3)):
        vehicles.append({
            "vehicle_id": vehicle_id_counter, "customer_id": customer_id,
            "make": "Best Automobile", "model": random.choice(model_types),
            "year": random.randint(2018, 2024),
            "vin": fake.unique.bothify(text="1HGBH41JXMN#####"),
        })
        for _ in range(random.randint(1, 4)):
            observed = random.sample(all_keys, random.randint(3, 6))
            parts, sev_by_comp = [], {}
            for ck in observed:
                text, sev = GENERATORS[ck]()
                parts.append(text)
                sev_by_comp[ck] = sev
            # Technician flags ONLY the single most-severe (an Urgent one, if any).
            urgents = [ck for ck, s in sev_by_comp.items() if s == "Urgent"]
            flagged = [random.choice(urgents)] if urgents else []
            services.append({
                "service_id": service_id_counter,
                "vehicle_id": vehicle_id_counter,
                "technician_id": random.randint(1, len(technicians)),
                "service_date": fake.date_between(start_date="-2y", end_date="today"),
                "service_type": random.choice(SERVICE_TYPES),
                "service_performed": " ".join(parts),
                "flagged_components": flagged,
                "ground_truth": json.dumps(sev_by_comp),
            })
            service_id_counter += 1
        vehicle_id_counter += 1

# Prepend curated demo rows with the lowest service_ids (1..N). They reference vehicle_id
# 1..N, which always exist (the random generation above creates hundreds of vehicles).
import datetime as _dt
_demo_date = _dt.date(2024, 5, 15)
demo_services = []
for _i, (_notes, _flagged, _gt) in enumerate(DEMO_SERVICES):
    demo_services.append({
        "service_id": _i + 1,
        "vehicle_id": _i + 1,
        "technician_id": (_i % len(technicians)) + 1,
        "service_date": _demo_date,
        "service_type": "Multi-point inspection",
        "service_performed": _notes,
        "flagged_components": _flagged,
        "ground_truth": json.dumps(_gt),
    })
services = demo_services + services

# COMMAND ----------

from pyspark.sql.types import (StructType, StructField, LongType, IntegerType,
                               StringType, DateType, ArrayType)

service_schema = StructType([
    StructField("service_id", LongType()),
    StructField("vehicle_id", LongType()),
    StructField("technician_id", IntegerType()),
    StructField("service_date", DateType()),
    StructField("service_type", StringType()),
    StructField("service_performed", StringType()),
    StructField("flagged_components", ArrayType(StringType())),
    StructField("ground_truth", StringType()),
])

df_customers = spark.createDataFrame(customers)
df_vehicles = spark.createDataFrame(vehicles)
df_technicians = spark.createDataFrame(technicians)
df_services = spark.createDataFrame(services, schema=service_schema)

df_customers.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("customer")
df_vehicles.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("vehicle")
df_technicians.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("technician")
df_services.write.format("delta").mode("overwrite").option("overwriteSchema", "true").saveAsTable("service")

print(f"Wrote {spark.table('customer').count()} customers, "
      f"{spark.table('vehicle').count()} vehicles, "
      f"{spark.table('service').count()} services to {catalog}.{schema}")
