"""
QSR Insights to Action Agent Dashboard - BigQuery ADK Tools
Defines functions for querying metrics, action items, and performing write-backs to BigQuery.
"""

from google.cloud import bigquery
import datetime

# Helper function to get a BigQuery client and resolve dataset/project
def _get_client():
    client = bigquery.Client(location="us-central1")
    return client, client.project

def get_store_metrics(store_id: str, current_date: str = "2026-05-28") -> list[dict]:
    """Get the trailing 10 days of operational KPIs for a specific store relative to a given date.
    
    Args:
        store_id: The ID of the store (e.g., 'dublin_hq', 'atlanta_peachtree')
        current_date: The active system date in YYYY-MM-DD format (defaults to "2026-05-28")
        
    Returns:
        A list of dictionaries containing daily metrics: date, drive_thru_avg_seconds,
        labor_cost_percentage, order_accuracy_rate, food_waste_lbs, gross_sales_usd.
    """
    client, project_id = _get_client()
    
    query = f"""
        SELECT 
            CAST(date AS STRING) as date, 
            store_id, 
            drive_thru_avg_seconds, 
            labor_cost_percentage, 
            order_accuracy_rate, 
            food_waste_lbs, 
            gross_sales_usd
        FROM `{project_id}.qsrs_agent_simulation.fact_daily_kpis`
        WHERE store_id = @store_id AND date <= @current_date
        ORDER BY date DESC
        LIMIT 10
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
            bigquery.ScalarQueryParameter("current_date", "STRING", current_date),
        ]
    )
    
    query_job = client.query(query, job_config=job_config, location="us-central1")
    results = query_job.result()
    
    metrics = []
    # Reverse so that it is ordered chronologically for plotting/analytics
    for row in reversed(list(results)):
        metrics.append({
            "date": row.date,
            "store_id": row.store_id,
            "drive_thru_avg_seconds": row.drive_thru_avg_seconds,
            "labor_cost_percentage": row.labor_cost_percentage,
            "order_accuracy_rate": row.order_accuracy_rate,
            "food_waste_lbs": row.food_waste_lbs,
            "gross_sales_usd": row.gross_sales_usd,
        })
        
    return metrics

def get_action_items(store_id: str, date: str = "2026-05-28") -> list[dict]:
    """Get the 10 prioritized daily action checklist items for a specific store and date.
    
    Args:
        store_id: The ID of the store (e.g., 'dublin_hq')
        date: The date in YYYY-MM-DD format (defaults to "2026-05-28")
        
    Returns:
        A list of 10 dictionaries containing prioritized action items.
    """
    client, project_id = _get_client()
    
    query = f"""
        SELECT 
            action_item_id, 
            CAST(date AS STRING) as date, 
            store_id, 
            priority_rank, 
            category, 
            insight_text, 
            action_text, 
            status, 
            CAST(updated_at AS STRING) as updated_at
        FROM `{project_id}.qsrs_agent_simulation.fact_action_items`
        WHERE store_id = @store_id AND date = @date
        ORDER BY priority_rank ASC
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("store_id", "STRING", store_id),
            bigquery.ScalarQueryParameter("date", "STRING", date),
        ]
    )
    
    query_job = client.query(query, job_config=job_config, location="us-central1")
    results = query_job.result()
    
    items = []
    for row in results:
        items.append({
            "action_item_id": row.action_item_id,
            "date": row.date,
            "store_id": row.store_id,
            "priority_rank": row.priority_rank,
            "category": row.category,
            "insight_text": row.insight_text,
            "action_text": row.action_text,
            "status": row.status,
            "updated_at": row.updated_at,
        })
        
    return items

def update_action_item_status(action_item_id: str, status: str) -> dict:
    """Update the compliance status (Done or Pending) of a specific action item in BigQuery.
    
    Args:
        action_item_id: The unique ID of the action item
        status: The target status to set (either 'Done' or 'Pending')
        
    Returns:
        A status dictionary indicating success or failure.
    """
    # Enforce status constraint
    if status not in ["Done", "Pending"]:
        raise ValueError("Status must be either 'Done' or 'Pending'")
        
    client, project_id = _get_client()
    
    # Run transaction update
    query = f"""
        UPDATE `{project_id}.qsrs_agent_simulation.fact_action_items`
        SET status = @status, updated_at = CURRENT_TIMESTAMP()
        WHERE action_item_id = @action_item_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("status", "STRING", status),
            bigquery.ScalarQueryParameter("action_item_id", "STRING", action_item_id),
        ]
    )
    
    query_job = client.query(query, job_config=job_config, location="us-central1")
    query_job.result()  # Wait for transaction to complete
    
    return {
        "success": True,
        "action_item_id": action_item_id,
        "status": status,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z"
    }

def get_action_item_context(action_item_id: str) -> tuple[str, str]:
    """Retrieve the store_id and date associated with a specific action item.
    
    Args:
        action_item_id: The unique ID of the action item
        
    Returns:
        A tuple of (store_id, date) strings.
    """
    client, project_id = _get_client()
    query = f"""
        SELECT store_id, CAST(date AS STRING) as date
        FROM `{project_id}.qsrs_agent_simulation.fact_action_items`
        WHERE action_item_id = @action_item_id
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("action_item_id", "STRING", action_item_id),
        ]
    )
    query_job = client.query(query, job_config=job_config, location="us-central1")
    results = list(query_job.result())
    if results:
        return results[0].store_id, results[0].date
    return "dublin_hq", "2026-05-28"

