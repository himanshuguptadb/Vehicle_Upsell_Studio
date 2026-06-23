"""DDL + seed data for the app's Delta tables.

Shared by the deploy-time setup script and the in-app "reset/seed" path. All DDL is
idempotent (CREATE ... IF NOT EXISTS / MERGE for the component seed).
"""
from __future__ import annotations

from .sql import sql_str

# component_key, display_name, description, rubric, sort_order
SEED_COMPONENTS: list[tuple[str, str, str, str, int]] = [
    ("tires", "Tires",
     "Tread depth, wear pattern, sidewall condition, age.",
     "Urgent: tread under 3/32\", sidewall cracks/bulges, exposed cords, severe dry rot. "
     "Upcoming: tread 3/32\"-4/32\", early sidewall cracking, age 5-6 years, mild cupping/feathering. "
     "Good: tread above 4/32\", even wear, no damage, under ~5 years.", 1),
    ("brakes", "Brake Pads",
     "Friction material thickness, noise, rotor condition.",
     "Urgent: pads under 2mm, grinding/metal-to-metal, brake warning light, rotor scoring. "
     "Upcoming: 3mm-4mm remaining, early squeal, light rotor scoring, glazing. "
     "Good: 5mm+ friction material, even wear, no noise, smooth rotors.", 2),
    ("battery", "Battery",
     "Voltage, cranking health, terminal corrosion, age.",
     "Urgent: failed load test, will not hold charge, severe corrosion. "
     "Upcoming: weak cranking, age 3-5 years, minor corrosion. Good: healthy voltage, clean terminals.", 3),
    ("suspension", "Suspension & Steering",
     "Shocks/struts, bushings, alignment, play in steering.",
     "Urgent: leaking struts, broken springs, unsafe play. "
     "Upcoming: worn bushings, alignment drift, early shock wear. Good: no play, rides level.", 4),
    ("engine_oil", "Engine Oil",
     "Oil color/viscosity, level, change interval.",
     "Urgent: very low/contaminated oil, metal particles. "
     "Upcoming: due for change soon, slightly dark. Good: clean oil, within interval.", 5),
    ("coolant", "Coolant",
     "Level, color/contamination, leaks.",
     "Urgent: low/contaminated coolant, visible leak, overheating. "
     "Upcoming: slightly low, due for flush. Good: correct level and condition.", 6),
    ("transmission_fluid", "Transmission Fluid",
     "Level, color, burnt smell.",
     "Urgent: burnt/very dark fluid, low level, shifting issues. "
     "Upcoming: darkening, due for service. Good: clean, correct level.", 7),
    ("belts_hoses", "Belts & Hoses",
     "Cracks, fraying, leaks on serpentine/timing belts and hoses.",
     "Urgent: cracked/frayed belt, leaking/swollen hose. "
     "Upcoming: minor cracking, age-based replacement nearing. Good: supple, no cracks.", 8),
    ("lights_electrical", "Lights & Electrical",
     "Headlights, indicators, wipers, electronics function.",
     "Urgent: non-functioning safety lights. Upcoming: dimming/intermittent, bulb nearing end. "
     "Good: all functioning.", 9),
    ("wipers", "Wiper Blades",
     "Streaking, tearing, chatter.",
     "Urgent: blades torn, large unswept areas. Upcoming: streaking/chatter starting. Good: clean wipe.", 10),
    ("exhaust", "Exhaust System",
     "Leaks, corrosion, noise, emissions.",
     "Urgent: exhaust leak, loud noise, failed emissions. Upcoming: surface corrosion, minor noise. "
     "Good: intact, quiet.", 11),
    ("ac", "Air Conditioning",
     "Cooling performance, refrigerant, cabin filter.",
     "Urgent: no cooling, compressor failure. Upcoming: weak cooling, dirty cabin filter. Good: cools well.", 12),
]


def ddl_statements() -> list[str]:
    return [
        """CREATE TABLE IF NOT EXISTS {components} (
            component_key STRING,
            display_name STRING,
            description STRING,
            rubric STRING,
            enabled BOOLEAN,
            sort_order INT
        ) USING DELTA""",
        """CREATE TABLE IF NOT EXISTS {configs} (
            config_id STRING,
            name STRING,
            description STRING,
            model_endpoint STRING,
            components STRING,
            prompt_text STRING,
            response_format STRING,
            created_by STRING,
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        ) USING DELTA""",
        """CREATE TABLE IF NOT EXISTS {runs} (
            run_id STRING,
            config_id STRING,
            config_name STRING,
            model_endpoint STRING,
            source_table STRING,
            row_count INT,
            created_at TIMESTAMP
        ) USING DELTA""",
        """CREATE TABLE IF NOT EXISTS {run_results} (
            run_id STRING,
            service_id BIGINT,
            component_key STRING,
            classification STRING,
            reasoning STRING
        ) USING DELTA""",
    ]


def seed_components_sql(table_fqn: str) -> str:
    """MERGE the seed components so re-running never duplicates rows."""
    values = ",\n".join(
        f"({sql_str(k)}, {sql_str(dn)}, {sql_str(desc)}, {sql_str(rub)}, true, {order})"
        for (k, dn, desc, rub, order) in SEED_COMPONENTS
    )
    return f"""
MERGE INTO {table_fqn} AS t
USING (
  SELECT * FROM VALUES
  {values}
  AS s(component_key, display_name, description, rubric, enabled, sort_order)
) AS s
ON t.component_key = s.component_key
WHEN NOT MATCHED THEN INSERT *
""".strip()
