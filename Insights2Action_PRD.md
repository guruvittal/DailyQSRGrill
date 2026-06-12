# Product Specification Document (PRD)

**Document Version:** V3.0  
**Author:** Seasoned Product Manager, Applied AI  
**Date:** May 28, 2026  
**Target Platform:** Gemini Enterprise Agent Platform  
**Frontend Framework:** Agent Application UI (A2UI) & Agent Sandbox Components  
**Development Framework:** Agent Development Kit (ADK)  
**Data Integration:** Native BigQuery Toolset  
**Data Infrastructure:** Google Cloud BigQuery  
**Environment Prototyping:** Antigravity Framework  

---

## 1. Executive Summary & Vision
QSR is establishing an **Insights to Action Agent Dashboard**—a premium, executive-grade AI application delivered natively inside Gemini Enterprise. Operating a Quick Service Restaurant (QSR) franchise demands rapid, data-backed interventions to manage razor-thin margins, labor allocations, and service velocity. Traditional static dashboards fail because they present data without automated, contextual interpretation.

This product bridges the analytical-operational gap. Rendered via **Agent Application UI (A2UI)** and powered by the **Agent Development Kit (ADK)**, the agent directly couples dynamic BigQuery insights with a sophisticated, conversational interface. It surfaces a curated list of the top daily operational action items alongside a classy dashboard of longitudinal KPIs, allowing franchise operators and executives to drive immediate compliance and monitor performance trends across real-world locations.

---

## 2. Product Objectives & Core Scope
* **Action-Oriented Leadership:** Dynamically generate and rank the **Top 10 daily action items** specific to each franchise store using real-time telemetry from BigQuery.
* **Time Travel Capabilities:** Give operators the explicit ability to "go back in time" up to **5 historical days** to audit past action items, review historic operational contexts, and track trailing compliance.
* **State Tracking & Compliance:** Provide interactive check-boxes allowing operators to mark individual tasks as **"Done"**, instantly persisting state back to BigQuery to monitor store adherence.
* **Longitudinal KPI Dashboards:** Display high-fidelity, classy charts mapping performance over a rolling **10-day window**, benchmarking individual store metrics against corporate or regional performance.
* **High-Fidelity Environment Bootstrapping:** Leverage the Antigravity framework to provision backend tables and auto-populate simulation data representing real-world flagship locations over a 1-month window to validate the agent's analytical capabilities.

---

## 3. Architecture & System Integration Blueprint
The system architecture migrates away from runtime middleware pipelines to leverage native Google Cloud enterprise agent tooling, maximizing security, reliability, and speed. Antigravity is utilized strictly for structural bootstrapping and initial data preparation.

| Layer / Component | Technology Stack | Operational Role |
| :--- | :--- | :--- |
| **Frontend Layer** | Agent Application UI (A2UI) | Renders the conversational interface, side-by-side agent layout, layouts for data cards, and action checklists. |
| **Data Visualization** | Agent Sandbox Components | Generates classy, responsive, high-fidelity charts and analytics widgets natively integrated inside the chat experience. |
| **Core Execution Logic** | Agent Development Kit (ADK) | Defines the core agent logic, manages system instructions, structures prompt context templates, and orchestrates tooling interactions. |
| **Data Connector** | BigQuery Toolset | Provides native, zero-middleware tools for Gemini to directly discover, query, and perform transactional write-backs to data warehouses. |
| **Data Layer** | Google Cloud BigQuery | Serves as the single source of truth for raw KPIs, historical snapshots, and real-time operator compliance state logs. |

---

## 4. Functional Requirements & User Experience (UX)

### 4.1 User Interface Architecture (A2UI & Agent Sandbox)
The dashboard utilizes a polished layout designed for executive-level presentation:
* **Conversational Command Panel:** A premium text panel greeting the operator with an LLM-synthesized operational overview of their specific store.
* **Top 10 Action List:** An interactive, clean checklist layout displaying prioritized operations, explicit reasoning, and an actionable checklist toggle. Toggling an item to Done updates a live progress indicator.
* **Time Travel Widget:** A date-selection carousel restricted to a rolling 5-day historical view. Changing the date updates both the action items list and freezes the historical data charts.
* **Sandbox Visualization Panel:** Rendered cleanly alongside the conversational panel, displaying 10-day rolling time-series charts for Speed of Service, Labor Costs, Order Accuracy, and Food Waste.

### 4.2 Tooling and Logic Specifications (ADK & Toolset)
* **Dynamic Data Retrieval:** Upon user authentication and initialization, the ADK agent invokes the BigQuery Toolset to query `fact_daily_kpis` and `fact_action_items` matching the operator's specific `store_id`.
* **State Synchronization:** When an operator marks an action item as completed, the ADK triggers a write-back query via the BigQuery Toolset, updating the status column to `Done` and stamping the `updated_at` field in real time.

---

## 5. BigQuery Schema Blueprint & Environment Setup
To simulate a realistic enterprise ecosystem for prototyping, the backend environment requires the definition of three core table structures. **The SQL provided below is strictly representative; the Antigravity framework has full autonomy to alter, refactor, or optimize this code as it deems fit to best achieve the seed data specifications.**

### 5.1 Table Schema Framework
```sql
-- Representative Data schema setup for QSR Agent Simulation
CREATE SCHEMA IF NOT EXISTS qsrs_agent_simulation;

-- 1. DIM_STORES: Store Metadata with Real-World Flagship Identifiers
CREATE OR REPLACE TABLE qsrs_agent_simulation.dim_stores (
  store_id STRING,
  store_name STRING,
  city STRING,
  region STRING
);

-- 2. FACT_DAILY_KPIS: Longitudinal Performance Logs
CREATE OR REPLACE TABLE qsrs_agent_simulation.fact_daily_kpis (
  date DATE,
  store_id STRING,
  drive_thru_avg_seconds FLOAT64,
  labor_cost_percentage FLOAT64,
  order_accuracy_rate FLOAT64,
  food_waste_lbs FLOAT64,
  gross_sales_usd FLOAT64
);

-- 3. FACT_ACTION_ITEMS: Action Item Records & Compliance State
CREATE OR REPLACE TABLE qsrs_agent_simulation.fact_action_items (
  action_item_id STRING,
  date DATE,
  store_id STRING,
  priority_rank INT64,
  category STRING,
  insight_text STRING,
  action_text STRING,
  status STRING,
  updated_at TIMESTAMP
);
```

---

## 6. Seed Generation Specifications (Instructions for Antigravity)
Antigravity should utilize the baseline schema above to construct and execute data pipelines that model a realistic 1-month trajectory. It should optimize the underlying queries to hit the following data parameters:

* **Flagship Entities:** Seed the store dimension table using explicit, real-world nomenclature rather than generic numeric identifiers. The locations must explicitly feature high-profile sites including:
  * *QSR - Dublin Corporate Headquarters*
  * *QSR - Highway 161 Costco Campus*
  * *QSR - Atlanta Peachtree Executive Center*
  * *QSR - Savannah Historic Riverfront*
* **Longitudinal Continuous History:** Generate 30 consecutive calendar days of comprehensive operational KPI telemetry across every store location to guarantee reliable historical baselines.
* **Targeted Operational Anomalies:** Intentionally engineer specific operational deviations over the trailing 10 days to validate the ADK Agent’s analysis engines. This includes systemic drive-thru bottlenecks at the *Dublin Corporate Headquarters* location, and conspicuous labor-cost spikes mid-month at the *Atlanta Peachtree Executive Center*.
* **Compliance & State Log Simulation:** Populate exactly 10 prioritized operational records per day for each store across a rolling 6-day window (today plus the 5 trailing days). Today's entries must default to a `Pending` status, while the prior 5 historical days must carry a randomized distribution of `Done` and `Pending` entries to test time-travel visibility and historical adherence reporting.

---

## 7. Non-Functional & Governance Standards
* **Security and Isolation:** All data queries resolved via the BigQuery Toolset must enforce session-based Row-Level Security (RLS) policies, guaranteeing that operators only view records bound to their designated `store_id`.
* **UI Responsiveness:** Dashboard components using the Agent Sandbox canvas must apply optimized column-indexing and partitioning on the BigQuery table structures to secure rendering refresh cycles under 1.5 seconds.
* **Write Transaction Handling:** State write-backs executing status modifications must resolve asynchronously, ensuring the client UI performance remains smooth.
