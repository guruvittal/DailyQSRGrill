#!/usr/bin/env python3
"""
QSR Insights to Action Agent Dashboard - Database Bootstrapping Script
Creates the BigQuery dataset and seeds dim_stores, fact_daily_kpis, and fact_action_items
with realistic QSR franchise operational metrics and anomalies.
"""

import sys
import datetime
import random
from google.cloud import bigquery

def main():
    print("🚀 Starting QSR Agent Simulation database bootstrapping...")

    # Initialize BigQuery client
    client = bigquery.Client()
    project_id = client.project
    print(f"Using Google Cloud Project: {project_id}")

    dataset_id = f"{project_id}.qsrs_agent_simulation"
    dataset = bigquery.Dataset(dataset_id)
    dataset.location = "us-central1"

    # Create dataset if not exists
    try:
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"✅ BigQuery dataset '{dataset_id}' created or already exists.")
    except Exception as e:
        print(f"❌ Failed to create dataset: {e}", file=sys.stderr)
        sys.exit(1)

    # 1. Define schemas and create tables
    # DIM_STORES
    dim_stores_table_id = f"{dataset_id}.dim_stores"
    dim_stores_schema = [
        bigquery.SchemaField("store_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("store_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("city", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
    ]
    
    # FACT_DAILY_KPIS
    fact_daily_kpis_table_id = f"{dataset_id}.fact_daily_kpis"
    fact_daily_kpis_schema = [
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("store_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("drive_thru_avg_seconds", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("labor_cost_percentage", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("order_accuracy_rate", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("food_waste_lbs", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("gross_sales_usd", "FLOAT64", mode="REQUIRED"),
    ]

    # FACT_ACTION_ITEMS
    fact_action_items_table_id = f"{dataset_id}.fact_action_items"
    fact_action_items_schema = [
        bigquery.SchemaField("action_item_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("date", "DATE", mode="REQUIRED"),
        bigquery.SchemaField("store_id", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("priority_rank", "INT64", mode="REQUIRED"),
        bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("insight_text", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("action_text", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("status", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="NULLABLE"),
    ]

    def recreate_table(table_id, schema):
        table = bigquery.Table(table_id, schema=schema)
        # We delete existing tables to perform a clean bootstrap seeding
        client.delete_table(table_id, not_found_ok=True)
        new_table = client.create_table(table)
        print(f"✅ Recreated table '{table_id}'")
        return new_table

    recreate_table(dim_stores_table_id, dim_stores_schema)
    recreate_table(fact_daily_kpis_table_id, fact_daily_kpis_schema)
    recreate_table(fact_action_items_table_id, fact_action_items_schema)

    # 2. Seed DIM_STORES
    stores = [
        {"store_id": "dublin_hq", "store_name": "QSR - Dublin Corporate Headquarters", "city": "Dublin", "region": "Midwest"},
        {"store_id": "costco_campus", "store_name": "QSR - Highway 161 Costco Campus", "city": "Dublin", "region": "Midwest"},
        {"store_id": "atlanta_peachtree", "store_name": "QSR - Atlanta Peachtree Executive Center", "city": "Atlanta", "region": "South"},
        {"store_id": "savannah_riverfront", "store_name": "QSR - Savannah Historic Riverfront", "city": "Savannah", "region": "South"},
    ]
    
    print("⏳ Seeding dim_stores...")
    errors = client.insert_rows_json(dim_stores_table_id, stores)
    if errors:
        print(f"❌ Errors seeding dim_stores: {errors}", file=sys.stderr)
        sys.exit(1)
    print("✅ Seeded dim_stores successfully.")

    # 3. Seed FACT_DAILY_KPIS (30 consecutive days from 2026-04-29 to 2026-05-28)
    start_date = datetime.date(2026, 4, 29)
    end_date = datetime.date(2026, 5, 28)
    delta = datetime.timedelta(days=1)

    daily_kpis = []
    current_date = start_date

    # Use a fixed seed for reproducible simulation trends
    random.seed(42)

    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        
        for store in stores:
            store_id = store["store_id"]
            
            # Baseline parameters
            dt_avg = random.uniform(130.0, 170.0)
            labor_pct = random.uniform(21.0, 25.0)
            accuracy = random.uniform(0.93, 0.98)
            waste_lbs = random.uniform(15.0, 28.0)
            sales = random.uniform(4500.0, 6200.0)

            # Apply targeted anomalies over trailing 10 days (May 19 to May 28)
            # 1) dublin_hq drive-thru average seconds spike to 280-350s
            if store_id == "dublin_hq" and datetime.date(2026, 5, 19) <= current_date <= datetime.date(2026, 5, 28):
                dt_avg = random.uniform(280.0, 350.0)
                accuracy -= random.uniform(0.02, 0.05) # collateral impact on accuracy
                sales -= random.uniform(300.0, 800.0)   # lost revenue due to drive-thru abandonment

            # 2) atlanta_peachtree labor cost spike mid-month (May 12 to May 18) to 38-46%
            if store_id == "atlanta_peachtree" and datetime.date(2026, 5, 12) <= current_date <= datetime.date(2026, 5, 18):
                labor_pct = random.uniform(38.0, 46.0)
                sales += random.uniform(100.0, 300.0) # slight increase in sales but disproportional labor

            # Adjustments for weekend vs weekday
            day_of_week = current_date.weekday() # 5 = Saturday, 6 = Sunday
            if day_of_week >= 5:
                sales *= 1.2
                waste_lbs *= 1.15
            
            daily_kpis.append({
                "date": date_str,
                "store_id": store_id,
                "drive_thru_avg_seconds": round(dt_avg, 2),
                "labor_cost_percentage": round(labor_pct, 2),
                "order_accuracy_rate": round(accuracy, 4),
                "food_waste_lbs": round(waste_lbs, 2),
                "gross_sales_usd": round(sales, 2)
            })

        current_date += delta

    print(f"⏳ Seeding fact_daily_kpis ({len(daily_kpis)} records)...")
    # Batch insert to avoid maximum payload issues
    chunk_size = 50
    for i in range(0, len(daily_kpis), chunk_size):
        chunk = daily_kpis[i:i+chunk_size]
        errors = client.insert_rows_json(fact_daily_kpis_table_id, chunk)
        if errors:
            print(f"❌ Errors seeding fact_daily_kpis chunk {i}: {errors}", file=sys.stderr)
            sys.exit(1)
    print("✅ Seeded fact_daily_kpis successfully.")

    # 4. Seed FACT_ACTION_ITEMS (Exactly 10 items per store per day for 6 days: May 23 to May 28)
    action_item_dates = [
        datetime.date(2026, 5, 23),
        datetime.date(2026, 5, 24),
        datetime.date(2026, 5, 25),
        datetime.date(2026, 5, 26),
        datetime.date(2026, 5, 27),
        datetime.date(2026, 5, 28) # Today
    ]

    # Pre-defined operational checklist categories and contents to make it look premium
    categories_pool = [
        {
            "category": "Speed",
            "insights": {
                "dublin_hq": "Drive-thru times spiked to {metric}s (Target: <150s) during lunch peak due to kitchen prep delay.",
                "default": "Drive-thru bottleneck detected at 12:30 PM with average timer at {metric}s."
            },
            "actions": {
                "dublin_hq": "Re-allocate sandwich assembly crew and assign dedicated order-taker to expedite drive-thru window.",
                "default": "Initiate double-lane prep protocol and verify order-ready timers are operational."
            }
        },
        {
            "category": "Labor",
            "insights": {
                "atlanta_peachtree": "Labor percentage is at {metric}% (Target: <25%) due to overstaffing relative to late afternoon sales drop.",
                "default": "Labor efficiency dipped to {metric}% with 3 idle shifts in midday transition."
            },
            "actions": {
                "atlanta_peachtree": "Implement immediate labor cutbacks for secondary prep shifts and re-align schedule with actual transaction velocity.",
                "default": "Cross-train front counter staff to assist with dining area maintenance to optimize hour utilization."
            }
        },
        {
            "category": "Quality",
            "insights": {
                "default": "Order accuracy fell to {metric}% (Target: >95%) due to customized sauce omission on Baconator orders."
            },
            "actions": {
                "default": "Enforce double-check validation on all customized drive-thru bags and run sandwich build refresher training."
            }
        },
        {
            "category": "Waste",
            "insights": {
                "default": "Over-prep of beef patties during late afternoon resulted in {metric} lbs of waste."
            },
            "actions": {
                "default": "Audit Fry/Grill prep sheets hourly and align patty cooking cycle with the automated POS velocity system."
            }
        },
        {
            "category": "Sales",
            "insights": {
                "default": "Upsell attachment rate for Dave's Single combos is below benchmark, impacting ticket size by ${metric}."
            },
            "actions": {
                "default": "Brief drive-thru crew on combo attachment goals and offer the high-margin frosty pairing promotion."
            }
        },
        {
            "category": "Safety",
            "insights": {
                "default": "Mid-afternoon walk-in cooler temperature logs were omitted. Food safety compliance requires strict logs."
            },
            "actions": {
                "default": "Designate shift supervisor to record cooler temperatures immediately and log into the safety tablet."
            }
        },
        {
            "category": "Cleanliness",
            "insights": {
                "default": "Customer feedback indicates drive-thru lane litter and dirty trash bins are spoiling the entrance aesthetic."
            },
            "actions": {
                "default": "Establish a 2-hour parking lot/drive-thru sweep schedule and pressure-wash outer dumpster pad."
            }
        },
        {
            "category": "Equipment",
            "insights": {
                "default": "Drive-thru headset channel 3 is experiencing static interference, slowing order taking efficiency."
            },
            "actions": {
                "default": "Replace defective batteries, clean terminal contacts, and escalate to technical hardware replacement if static persists."
            }
        },
        {
            "category": "Inventory",
            "insights": {
                "default": "Crushed ice stock is running critically low due to ice-maker condenser blockage."
            },
            "actions": {
                "default": "Manually clear debris from ice-maker ventilation fan and source fallback bag ice from local distributor."
            }
        },
        {
            "category": "Customer",
            "insights": {
                "default": "Overall CSAT rating dropped slightly because of extended wait times for mobile order pickup stalls."
            },
            "actions": {
                "default": "Repaint parking lines for mobile spots and assign designated runner for expedited curbside dispatch."
            }
        }
    ]

    action_items = []

    for store in stores:
        store_id = store["store_id"]
        
        for date_obj in action_item_dates:
            date_str = date_obj.strftime("%Y-%m-%d")
            
            # Find the KPIs of this store and day for embedding in the insights
            kpi_match = next((k for k in daily_kpis if k["store_id"] == store_id and k["date"] == date_str), None)
            
            # Create exactly 10 prioritized action items (ranks 1 to 10)
            for rank in range(1, 11):
                item_pool = categories_pool[rank - 1]
                category = item_pool["category"]
                
                # Determine metric to show in insight
                if category == "Speed":
                    metric_val = str(int(kpi_match["drive_thru_avg_seconds"])) if kpi_match else "315"
                elif category == "Labor":
                    metric_val = str(kpi_match["labor_cost_percentage"]) if kpi_match else "39.5"
                elif category == "Quality":
                    metric_val = str(round((kpi_match["order_accuracy_rate"] * 100), 1)) if kpi_match else "91.5"
                elif category == "Waste":
                    metric_val = str(kpi_match["food_waste_lbs"]) if kpi_match else "24.2"
                elif category == "Sales":
                    metric_val = "1.45"
                else:
                    metric_val = "N/A"

                # Pull insight/action texts
                if store_id in item_pool["insights"]:
                    insight_tpl = item_pool["insights"][store_id]
                else:
                    insight_tpl = item_pool["insights"]["default"]
                    
                if store_id in item_pool["actions"]:
                    action_tpl = item_pool["actions"][store_id]
                else:
                    action_tpl = item_pool["actions"]["default"]
                    
                insight_text = insight_tpl.format(metric=metric_val)
                action_text = action_tpl.format(metric=metric_val)

                # Set status: Today (May 28) is all Pending, other days are random
                if date_obj == datetime.date(2026, 5, 28):
                    status = "Pending"
                    updated_at = None
                else:
                    status = "Done" if random.random() < 0.6 else "Pending"
                    updated_at = f"{date_str}T16:00:00Z" if status == "Done" else None

                action_item_id = f"{store_id}-{date_str.replace('-', '')}-{rank:02d}"

                action_items.append({
                    "action_item_id": action_item_id,
                    "date": date_str,
                    "store_id": store_id,
                    "priority_rank": rank,
                    "category": category,
                    "insight_text": insight_text,
                    "action_text": action_text,
                    "status": status,
                    "updated_at": updated_at
                })

    print(f"⏳ Seeding fact_action_items ({len(action_items)} records)...")
    # Batch insert action items
    for i in range(0, len(action_items), chunk_size):
        chunk = action_items[i:i+chunk_size]
        errors = client.insert_rows_json(fact_action_items_table_id, chunk)
        if errors:
            print(f"❌ Errors seeding fact_action_items chunk {i}: {errors}", file=sys.stderr)
            sys.exit(1)
    
    print("✅ Seeded fact_action_items successfully.")
    print("🎉 QSR Agent Simulation database bootstrapping completed successfully!")

if __name__ == "__main__":
    main()
