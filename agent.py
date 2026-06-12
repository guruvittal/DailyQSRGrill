"""
QSR Insights to Action Agent Dashboard - ADK Agent Configuration
Initializes the Gemini Enterprise-compatible ADK Agent, sets up tools,
and generates Lit/v0.8 compliant A2UI dashboards.
"""

import os
import re
# Configure environment variables to use Vertex AI dynamically
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
if "GOOGLE_CLOUD_PROJECT" not in os.environ:
    os.environ["GOOGLE_CLOUD_PROJECT"] = "vertexsearch-447722"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

from google.adk.agents.llm_agent import Agent
from google.genai import types
from a2ui.schema.constants import VERSION_0_8, VERSION_0_9
from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.catalog import CatalogConfig
from tools import get_store_metrics, get_action_items, update_action_item_status, get_action_item_context
from a2ui_utils import a2ui_callback

# 1. Initialize A2UI Schema Managers for both v0.8 and v0.9
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
vegalite_08_path = os.path.join(BASE_DIR, "catalog_schemas", "0.8", "vegalite_catalog_definition.json")
vegalite_09_path = os.path.join(BASE_DIR, "catalog_schemas", "0.9", "vegalite_catalog_definition.json")

schema_managers = {
    VERSION_0_8: A2uiSchemaManager(
        version=VERSION_0_8,
        catalogs=[
            BasicCatalog.get_config(VERSION_0_8),
            CatalogConfig.from_path(
                name="vegalite",
                catalog_path=vegalite_08_path
            )
        ],
    ),
    VERSION_0_9: A2uiSchemaManager(
        version=VERSION_0_9,
        catalogs=[
            BasicCatalog.get_config(VERSION_0_9),
            CatalogConfig.from_path(
                name="vegalite",
                catalog_path=vegalite_09_path
            )
        ],
    ),
}
schema_manager = schema_managers[VERSION_0_8]


# 2. Design the premium role and UI instructions
role_description = (
    "You are the QSR Insights-to-Action Executive Agent, designed to assist "
    "franchise operators and executives in managing their stores. "
    "You have access to Google Cloud BigQuery tools to retrieve trailing 10-day "
    "KPI trends, daily prioritized operations checklists (top 10 action items), "
    "and perform live compliance write-backs (marking items as Done or Pending).\n\n"
    "When a user asks about a store (e.g., 'dublin_hq', 'costco_campus', 'atlanta_peachtree', 'savannah_riverfront') "
    "or asks to view a dashboard or specific date, you must first call both tools: "
    "`get_store_metrics(store_id, current_date)` and `get_action_items(store_id, date)`. "
    "Use today's date (defaults to '2026-05-28') unless the user requests a different date.\n"
    "With the tools' results, you MUST return a single valid A2UI JSON array rendering a gorgeous, "
    "high-fidelity executive dashboard complying with the v0.8 specification.\n\n"
    "If the user greets you (e.g., 'hi', 'hello', 'greetings') or explicitly asks to go back to the welcome hub, do NOT call any tools. "
    "Instead, you MUST return a valid A2UI JSON array rendering a gorgeous, premium Welcome/Landing Dashboard.\n"
    "However, if the user asks general questions about metrics, KPIs, checklists, or trends but does not specify a store, "
    "you must default the store_id to 'dublin_hq' and proceed to call `get_store_metrics('dublin_hq', current_date)` "
    "and `get_action_items('dublin_hq', date)` to render the store dashboard for Dublin Corporate Headquarters. "
    "Do NOT display the Welcome/Landing Dashboard for analytical or metric-related queries."
)

workflow_description = (
    "1. Read the user's intent. Identify if they want to: \n"
    "   a. View/manage a specific store_id (e.g., 'dublin_hq', 'costco_campus', 'atlanta_peachtree', 'savannah_riverfront') and date.\n"
    "   b. Update an action item's status (e.g. user asks to 'Update compliance status of action item...').\n"
    "2. If the user greets you (e.g. they say 'hi') or asks to go to the welcome/landing hub, you MUST build and return the Welcome/Landing Dashboard. If they ask about metrics, trends, compliance, or checklists without specifying a store, default the store_id to 'dublin_hq' and proceed with step 4.\n"
    "3. If an update action is specified, you MUST call the tool `update_action_item_status(action_item_id, status)`. After updating, you must then call `get_action_items(store_id, date)` and `get_store_metrics(store_id, current_date)` for the store and date context associated with that action item (remembering/retaining the active store_id and date from conversational context/memory) to retrieve the updated data.\n"
    "4. If a store IS specified (or defaulted to 'dublin_hq'), invoke `get_store_metrics` and `get_action_items` for the target store.\n"
    "5. Based on the returned rows, build the Store Dashboard A2UI JSON response and output ONLY the JSON. Do not include any text or backticks outside the JSON."
)

ui_description = (
    "Your output MUST be a valid A2UI JSON array consisting of exactly two messages: "
    "a 'beginRendering' message followed by a 'surfaceUpdate' message.\n\n"
    "Ensure you follow these design and schema constraints:\n"
    "**CRITICAL BUTTON SCHEMA RULE (v0.8 COMPLIANCE):**\n"
    "In A2UI v0.8, the `child` property of a `Button` component MUST ALWAYS be a simple string ID referencing a separate `Text` component defined in the `components` list.\n"
    "- NEVER nest any objects or JSON dictionaries inside `Button.child` (e.g., do NOT do: `\"child\": { \"Text\": { ... } }` or `\"child\": { \"literalString\": ... }`). This triggers severe client-side form validation errors!\n"
    "- ALWAYS use a separate `Text` component for button label text, and point the Button's `child` property to that Text component's string ID (e.g., `\"child\": \"my_btn_text_id\"`).\n"
    "- This strict string ID requirement applies to EVERY button in your output, including:\n"
    "  1. The 4 store selection buttons on the welcome hub.\n"
    "  2. The 5 date navigation buttons on the store dashboard.\n"
    "  3. All 'Mark Done' / 'Mark Pending' checklist buttons.\n\n"
    "- Gemini Enterprise mandates Lit web components, which are rendered from the standard v0.8 catalog.\n"
    "- Do NOT use raw markdown (e.g., '#', '##', '**') inside Text component text values. Use the `usageHint` property (e.g. 'h1', 'h2') for heading levels instead.\n"
    "- Set `surfaceId` to 'default'.\n"
    "- Set `root` to 'dashboard_root'.\n\n"
    "Structure 'dashboard_root' as a Column.\n\n"
    "**If no store was specified (Welcome/Landing Dashboard), the children components of 'dashboard_root' MUST be in this exact order:**\n"
    "1. `greeting_card` (Card) - Displays the Hub Welcome and capabilities. "
    "The card's child is a Column containing:\n"
    "   - A Text component with usageHint 'h1' showing 'QSR Insights-to-Action Executive Hub'.\n"
    "   - A Text component showing a premium synthesized operational greeting: 'Welcome Operator! I am your AI executive partner. I track metrics, prioritize daily operations checklists, and update compliance across your franchise locations. Select a location below to begin.'\n"
    "2. `store_selection_card` (Card) - Displays store quick links. "
    "The card's child is a Column containing:\n"
    "   - A Text component with usageHint 'h2' ('Select a Franchise Location to Manage').\n"
    "   - A Row containing 4 store quick links as buttons:\n"
    "     - Dublin Corporate HQ (id: 'store_btn_dublin'): Button labeled 'Dublin Corporate HQ'. Its action is 'get_action_items' with context parameters: store_id: 'dublin_hq', date: '2026-05-28'.\n"
    "     - Atlanta Peachtree (id: 'store_btn_atlanta'): Button labeled 'Atlanta Peachtree'. Its action is 'get_action_items' with context parameters: store_id: 'atlanta_peachtree', date: '2026-05-28'.\n"
    "     - Costco Campus (id: 'store_btn_costco'): Button labeled 'Costco Campus'. Its action is 'get_action_items' with context parameters: store_id: 'costco_campus', date: '2026-05-28'.\n"
    "     - Savannah Riverfront (id: 'store_btn_savannah'): Button labeled 'Savannah Riverfront'. Its action is 'get_action_items' with context parameters: store_id: 'savannah_riverfront', date: '2026-05-28'.\n\n"
    "**If a store WAS specified (Store Dashboard), the children components of 'dashboard_root' MUST be in this exact order:**\n"
    "1. `greeting_card` (Card) - Displays the Store Header and Executive Telemetry Summary. "
    "The card's child is a Column containing:\n"
    "   - A Text component with usageHint 'h1' showing the beautiful store name (e.g., 'QSR - Dublin Corporate Headquarters').\n"
    "   - A Text component showing a premium synthesized operational greeting and highlights of today's KPI metrics.\n"
    "2. `date_carousel_card` (Card) - Displays the 'Time Travel' date navigation bar. "
    "The card's child is a Column containing:\n"
    "   - A Text component with usageHint 'h2' ('Select Date Context (5-Day Rolling History)').\n"
    "   - A Row containing 5 date selector buttons (dates '2026-05-24', '2026-05-25', '2026-05-26', '2026-05-27', '2026-05-28').\n"
    "     Each Button must have an action of name 'get_action_items' and a context array with store_id and date parameters (as literalString).\n"
    "3. `checklist_card` (Card) - Displays the prioritized Daily Operational Action Checklist. "
    "The card's child is a Column containing:\n"
    "   - A Text component with usageHint 'h2' ('Top 10 Daily Operational Actions').\n"
    "   - A Text component (id: 'compliance_progress_text') representing a high-fidelity visual progress bar. You MUST calculate this progress from the 10 retrieved action items. Count the number of items with status 'Done' (out of 10), and draw a solid block progress bar using Unicode characters. For example, if 6 items are Done, draw `Compliance Progress: [██████░░░░] 60% Done (6/10 items resolved)`. If 3 items are Done, draw `Compliance Progress: [███░░░░░░░] 30% Done (3/10 items resolved)`. If 10 items are Done, draw `Compliance Progress: [██████████] 100% Done (10/10 items resolved)`. This must be a clean, premium visual line.\n"
    "   - A List component. Its children are the 10 prioritized action items.\n"
    "     Each item is a Row or nested Column component with components:\n"
    "       - A Text component displaying: '[Rank] Category: Insight -> Action' (bolded/styled without raw markdown).\n"
    "       - A Button component labeled 'Mark Done' (if the item's current status is 'Pending', which fires action 'update_action_item_status' with status 'Done') or 'Mark Pending' (if the item's current status is 'Done', which fires action 'update_action_item_status' with status 'Pending'). "
    "The button's action name is 'update_action_item_status' and context contains 'action_item_id' and 'status' literalStrings.\n"
    "4. `trends_card` (Card) - Displays the premium Sandbox Longitudinal KPI Trends. "
    "The card's child is a Column containing:\n"
    "   - A Text component with usageHint 'h2' ('Trailing 10-Day Longitudinal Operational Trends').\n"
    "   - For each of the 4 KPIs (Speed of Service, Labor Cost, Order Accuracy, Food Waste), a Row component containing:\n"
    "     - A Text component describing the KPI name and current value (e.g., 'Drive-Thru Avg: 312s').\n"
    "     - A Text component displaying a high-fidelity unicode sparkline trend representing the 10-day history (e.g., '▃▄▅▇▇███▇' or similar block sparkline), plus the target benchmark.\n\n"
    "Let's make sure the JSON syntax is perfect, valid, and contains unique IDs for all components. Do NOT output any backticks or explanatory text outside the JSON."
)

# 3. Assemble the final prompt including schemas and examples
instruction = schema_manager.generate_system_prompt(
    role_description=role_description,
    workflow_description=workflow_description,
    ui_description=ui_description,
    include_schema=True,
    include_examples=True,
)

# 4. Define the Agent instance
root_agent = Agent(
    model="gemini-2.5-flash",
    name="qsr_dashboard",
    description="QSR Insights to Action Agent Dashboard providing executive management, compliance tracking, and longitudinal analytics.",
    instruction=instruction,
    tools=[get_store_metrics, get_action_items, update_action_item_status],
    after_model_callback=a2ui_callback,
    generate_content_config=types.GenerateContentConfig(
        temperature=0.0,
    ),
)


# 5. Define QSRAgent wrapper for A2A / Gemini Enterprise
from typing import Any, Optional, AsyncIterable
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    DataPart,
    TextPart,
)
from a2ui.a2a.extension import get_a2ui_agent_extension
import logging

logger = logging.getLogger(__name__)

class QSRAgent:
  """A2A-compliant wrapper for the QSR Insights-to-Action ADK Agent."""

  SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

  def __init__(self, base_url: str):
    self.base_url = base_url
    self._agent_card = self._build_agent_card()
    from google.adk.sessions.in_memory_session_service import InMemorySessionService
    self._session_service = InMemorySessionService()

  @property
  def agent_card(self) -> AgentCard:
    return self._agent_card

  def _build_agent_card(self) -> AgentCard:
    extensions = [
        get_a2ui_agent_extension(
            "0.8",
            True, # accepts_inline_catalogs
            ["https://a2ui.org/specification/v0_8/standard_catalog_definition.json"],
        ),
        get_a2ui_agent_extension(
            "0.9",
            True, # accepts_inline_catalogs
            ["https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"],
        )
    ]

    capabilities = AgentCapabilities(
        streaming=True,
        extensions=extensions,
    )
    skill = AgentSkill(
        id="qsr_dashboard",
        name="QSR Insights Dashboard",
        description=(
            "Provides executive dashboard analytics, checklist management, and compliance actions."
        ),
        tags=["dashboard", "operational", "compliance", "analytics"],
        examples=["Show me the dashboard for dublin_hq", "Update compliance status of item 1"],
    )

    return AgentCard(
        name="QSR Dashboard Agent",
        description="QSR Insights to Action Agent Dashboard providing executive management, compliance tracking, and longitudinal analytics.",
        url=self.base_url,
        version="1.0.0",
        default_input_modes=QSRAgent.SUPPORTED_CONTENT_TYPES,
        default_output_modes=QSRAgent.SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        skills=[skill],
    )

  def _make_sparkline(self, values: list[float]) -> str:
    if not values:
      return ""
    if len(values) == 1:
      return "▄"
    min_val = min(values)
    max_val = max(values)
    if min_val == max_val:
      return "▄" * len(values)
    spark_chars = ["\u2581", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
    result = []
    for v in values:
      idx = int((v - min_val) / (max_val - min_val) * (len(spark_chars) - 1))
      result.append(spark_chars[idx])
    return " ".join(result)

  def _render_welcome_dashboard(self) -> dict[str, Any]:
    md_text = "👋 Welcome Operator! Rendering the **QSR Insights-to-Action Executive Hub** below:"
    
    v08_components = [
        {
            "id": "dashboard_root",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["greeting_card", "store_selection_card"]
                    }
                }
            }
        },
        {
            "id": "greeting_card",
            "component": {
                "Card": {
                    "child": "greeting_column"
                }
            }
        },
        {
            "id": "greeting_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["greeting_h1", "greeting_text"]
                    }
                }
            }
        },
        {
            "id": "greeting_h1",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "QSR Insights-to-Action Executive Hub"
                    },
                    "usageHint": "h1"
                }
            }
        },
        {
            "id": "greeting_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Welcome Operator! I am your AI executive partner. I track metrics, prioritize daily operations checklists, and update compliance across your franchise locations. Select a location below to begin."
                    }
                }
            }
        },
        {
            "id": "store_selection_card",
            "component": {
                "Card": {
                    "child": "store_selection_column"
                }
            }
        },
        {
            "id": "store_selection_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["store_selection_h2", "store_buttons_row"]
                    }
                }
            }
        },
        {
            "id": "store_selection_h2",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Select a Franchise Location to Manage"
                    },
                    "usageHint": "h2"
                }
            }
        },
        {
            "id": "store_buttons_row",
            "component": {
                "Row": {
                    "children": {
                        "explicitList": [
                            "store_btn_dublin",
                            "store_btn_atlanta",
                            "store_btn_costco",
                            "store_btn_savannah"
                        ]
                    },
                    "distribution": "spaceEvenly"
                }
            }
        },
        {
            "id": "store_btn_dublin",
            "component": {
                "Button": {
                    "child": "store_btn_dublin_text",
                    "action": {
                        "name": "get_action_items",
                        "context": [
                            {"key": "store_id", "value": {"literalString": "dublin_hq"}},
                            {"key": "date", "value": {"literalString": "2026-05-28"}}
                        ]
                    }
                }
            }
        },
        {
            "id": "store_btn_dublin_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Dublin Corporate HQ"
                    }
                }
            }
        },
        {
            "id": "store_btn_atlanta",
            "component": {
                "Button": {
                    "child": "store_btn_atlanta_text",
                    "action": {
                        "name": "get_action_items",
                        "context": [
                            {"key": "store_id", "value": {"literalString": "atlanta_peachtree"}},
                            {"key": "date", "value": {"literalString": "2026-05-28"}}
                        ]
                    }
                }
            }
        },
        {
            "id": "store_btn_atlanta_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Atlanta Peachtree"
                    }
                }
            }
        },
        {
            "id": "store_btn_costco",
            "component": {
                "Button": {
                    "child": "store_btn_costco_text",
                    "action": {
                        "name": "get_action_items",
                        "context": [
                            {"key": "store_id", "value": {"literalString": "costco_campus"}},
                            {"key": "date", "value": {"literalString": "2026-05-28"}}
                        ]
                    }
                }
            }
        },
        {
            "id": "store_btn_costco_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Costco Campus"
                    }
                }
            }
        },
        {
            "id": "store_btn_savannah",
            "component": {
                "Button": {
                    "child": "store_btn_savannah_text",
                    "action": {
                        "name": "get_action_items",
                        "context": [
                            {"key": "store_id", "value": {"literalString": "savannah_riverfront"}},
                            {"key": "date", "value": {"literalString": "2026-05-28"}}
                        ]
                    }
                }
            }
        },
        {
            "id": "store_btn_savannah_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Savannah Riverfront"
                    }
                }
            }
        }
    ]

    ui_json = [
        {
            "beginRendering": {
                "surfaceId": "default",
                "catalogId": "https://a2ui.org/specification/v0_8/standard_catalog_definition.json",
                "root": "dashboard_root",
                "styles": {
                    "primaryColor": "#cc1a1a",
                    "font": "Outfit"
                }
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "default",
                "components": v08_components
            }
        }
    ]

    parts = [Part(root=TextPart(text=md_text))]
    parts.extend([Part(root=DataPart(data=item, metadata={"mimeType": "application/json+a2ui"})) for item in ui_json])

    return {
        "is_task_complete": True,
        "parts": parts
    }

  def _render_welcome_dashboard_v09(self) -> dict[str, Any]:
    md_text = "👋 Welcome Operator! Rendering the **QSR Insights-to-Action Executive Hub** below:"
    
    v09_components = [
        {
            "id": "dashboard_root",
            "component": "Column",
            "children": ["greeting_card", "store_selection_card"]
        },
        {
            "id": "greeting_card",
            "component": "Card",
            "child": "greeting_column"
        },
        {
            "id": "greeting_column",
            "component": "Column",
            "children": ["greeting_h1", "greeting_text"]
        },
        {
            "id": "greeting_h1",
            "component": "Text",
            "text": "QSR Insights-to-Action Executive Hub",
            "variant": "h1"
        },
        {
            "id": "greeting_text",
            "component": "Text",
            "text": "Welcome Operator! I am your AI executive partner. I track metrics, prioritize daily operations checklists, and update compliance across your franchise locations. Select a location below to begin.",
            "variant": "body"
        },
        {
            "id": "store_selection_card",
            "component": "Card",
            "child": "store_selection_column"
        },
        {
            "id": "store_selection_column",
            "component": "Column",
            "children": ["store_selection_h2", "store_buttons_row"]
        },
        {
            "id": "store_selection_h2",
            "component": "Text",
            "text": "Select a Franchise Location to Manage",
            "variant": "h2"
        },
        {
            "id": "store_buttons_row",
            "component": "Row",
            "children": [
                "store_btn_dublin",
                "store_btn_atlanta",
                "store_btn_costco",
                "store_btn_savannah"
            ],
            "distribution": "spaceEvenly"
        },
        {
            "id": "store_btn_dublin",
            "component": "Button",
            "child": "store_btn_dublin_text",
            "action": {
                "event": {
                    "name": "get_action_items",
                    "context": {
                        "store_id": "dublin_hq",
                        "date": "2026-05-28"
                    }
                }
            }
        },
        {
            "id": "store_btn_dublin_text",
            "component": "Text",
            "text": "Dublin Corporate HQ"
        },
        {
            "id": "store_btn_atlanta",
            "component": "Button",
            "child": "store_btn_atlanta_text",
            "action": {
                "event": {
                    "name": "get_action_items",
                    "context": {
                        "store_id": "atlanta_peachtree",
                        "date": "2026-05-28"
                    }
                }
            }
        },
        {
            "id": "store_btn_atlanta_text",
            "component": "Text",
            "text": "Atlanta Peachtree"
        },
        {
            "id": "store_btn_costco",
            "component": "Button",
            "child": "store_btn_costco_text",
            "action": {
                "event": {
                    "name": "get_action_items",
                    "context": {
                        "store_id": "costco_campus",
                        "date": "2026-05-28"
                    }
                }
            }
        },
        {
            "id": "store_btn_costco_text",
            "component": "Text",
            "text": "Costco Campus"
        },
        {
            "id": "store_btn_savannah",
            "component": "Button",
            "child": "store_btn_savannah_text",
            "action": {
                "event": {
                    "name": "get_action_items",
                    "context": {
                        "store_id": "savannah_riverfront",
                        "date": "2026-05-28"
                    }
                }
            }
        },
        {
            "id": "store_btn_savannah_text",
            "component": "Text",
            "text": "Savannah Riverfront"
        }
    ]

    ui_json = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "default",
                "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json",
                "root": "dashboard_root",
                "theme": {
                    "primaryColor": "#cc1a1a",
                    "font": "Outfit"
                }
            }
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "default",
                "components": v09_components
            }
        }
    ]

    parts = [Part(root=TextPart(text=md_text))]
    parts.extend([Part(root=DataPart(data=item, metadata={"mimeType": "application/json+a2ui"})) for item in ui_json])

    return {
        "is_task_complete": True,
        "parts": parts
    }

  def _render_store_dashboard(self, store_id: str, date: str) -> dict[str, Any]:
    # Query BigQuery
    metrics = get_store_metrics(store_id, date)
    checklist = get_action_items(store_id, date)
    
    # Get latest metrics for numbers
    latest_metrics = metrics[-1] if metrics else {}
    speed_val = latest_metrics.get("drive_thru_avg_seconds", 0)
    labor_val = latest_metrics.get("labor_cost_percentage", 0.0)
    accuracy_val = latest_metrics.get("order_accuracy_rate", 0.0)
    accuracy_pct = accuracy_val * 100
    waste_val = latest_metrics.get("food_waste_lbs", 0.0)
    
    # Generate sparks
    speed_spark = self._make_sparkline([m.get("drive_thru_avg_seconds", 0) for m in metrics])
    labor_spark = self._make_sparkline([m.get("labor_cost_percentage", 0.0) for m in metrics])
    accuracy_spark = self._make_sparkline([m.get("order_accuracy_rate", 0.0) for m in metrics])
    waste_spark = self._make_sparkline([m.get("food_waste_lbs", 0.0) for m in metrics])
    
    speed_status = "🟢 OPTIMAL" if speed_val < 300 else "🔴 ELEVATED"
    labor_status = "🟢 OPTIMAL" if labor_val < 22.0 else "⚠️ ELEVATED"
    accuracy_status = "🟢 OPTIMAL" if accuracy_pct >= 98.0 else "⚠️ BELOW BENCHMARK"
    waste_status = "🟢 OPTIMAL" if waste_val < 15.0 else "⚠️ ELEVATED"
    
    # Synthesis operational summary
    store_names = {
        "dublin_hq": "Dublin Corporate Headquarters",
        "atlanta_peachtree": "Atlanta Peachtree",
        "costco_campus": "Costco Campus",
        "savannah_riverfront": "Savannah Riverfront",
    }
    store_name = store_names.get(store_id, store_id.replace("_", " ").title())
    
    highlights = []
    if speed_val > 300:
        highlights.append(f"Drive-thru speed is elevated at {speed_val}s (target: <300s).")
    else:
        highlights.append(f"Drive-thru avg speed is excellent at {speed_val}s.")
        
    if labor_val > 22.0:
        highlights.append(f"Labor cost is slightly elevated at {labor_val}% (target: 22%).")
    else:
        highlights.append(f"Labor cost is optimized at {labor_val}%.")
        
    if accuracy_pct < 98.0:
        highlights.append(f"Order accuracy ({accuracy_pct:.2f}%) is below our 98% benchmark.")
    else:
        highlights.append(f"Order accuracy is exceptional at {accuracy_pct:.2f}%.")
        
    summary_text = f"Executive Telemetry Summary: {store_name} on {date}. " + " ".join(highlights)
    md_text = f"📊 Rendering the **{store_name}** dashboard context below:"

    components = []
    
    # Root
    components.append({
        "id": "dashboard_root",
        "component": {
            "Column": {
                "children": {
                    "explicitList": ["greeting_card", "date_carousel_card", "checklist_card", "trends_card"]
                }
            }
        }
    })
    
    # Greeting Card
    components.extend([
        {
            "id": "greeting_card",
            "component": {
                "Card": {
                    "child": "greeting_column"
                }
            }
        },
        {
            "id": "greeting_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["greeting_h1", "greeting_text"]
                    }
                }
            }
        },
        {
            "id": "greeting_h1",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"QSR - {store_name}"
                    },
                    "usageHint": "h1"
                }
            }
        },
        {
            "id": "greeting_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": summary_text
                    }
                }
            }
        }
    ])
    
    # Date Carousel Card
    carousel_dates = ["2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28"]
    date_btn_ids = [f"date_btn_{d}" for d in carousel_dates]
    
    components.extend([
        {
            "id": "date_carousel_card",
            "component": {
                "Card": {
                    "child": "date_carousel_column"
                }
            }
        },
        {
            "id": "date_carousel_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["date_carousel_h2", "date_carousel_row"]
                    }
                }
            }
        },
        {
            "id": "date_carousel_h2",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Select Date Context (5-Day Rolling History)"
                    },
                    "usageHint": "h2"
                }
            }
        },
        {
            "id": "date_carousel_row",
            "component": {
                "Row": {
                    "children": {
                        "explicitList": date_btn_ids
                    },
                    "distribution": "spaceEvenly"
                }
            }
        }
    ])
    
    for d in carousel_dates:
        components.extend([
            {
                "id": f"date_btn_{d}",
                "component": {
                    "Button": {
                        "child": f"date_btn_text_{d}",
                        "action": {
                            "name": "get_action_items",
                            "context": [
                                {"key": "store_id", "value": {"literalString": store_id}},
                                {"key": "date", "value": {"literalString": d}}
                            ]
                        }
                    }
                }
            },
            {
                "id": f"date_btn_text_{d}",
                "component": {
                    "Text": {
                        "text": {
                            "literalString": d
                        }
                    }
                }
            }
        ])
        
    # Checklist Card
    done_count = sum(1 for item in checklist if item["status"] == "Done")
    total_count = len(checklist) if checklist else 10
    progress_pct = int(done_count / total_count * 100) if total_count > 0 else 0
    solid_blocks = done_count
    empty_blocks = total_count - done_count
    progress_bar = f"Compliance Progress: [{'█' * solid_blocks}{'░' * empty_blocks}] {progress_pct}% Done ({done_count}/{total_count} items resolved)"
    
    checklist_row_ids = [f"checklist_row_{i}" for i in range(len(checklist))]
    
    components.extend([
        {
            "id": "checklist_card",
            "component": {
                "Card": {
                    "child": "checklist_column"
                }
            }
        },
        {
            "id": "checklist_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["checklist_h2", "compliance_progress_text", "checklist_list"]
                    }
                }
            }
        },
        {
            "id": "checklist_h2",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Top 10 Daily Operational Actions"
                    },
                    "usageHint": "h2"
                }
            }
        },
        {
            "id": "compliance_progress_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": progress_bar
                    }
                }
            }
        },
        {
            "id": "checklist_list",
            "component": {
                "List": {
                    "children": {
                        "explicitList": checklist_row_ids
                    }
                }
            }
        }
    ])
    
    for i, item in enumerate(checklist):
        row_id = f"checklist_row_{i}"
        btn_id = f"item_btn_{i}"
        btn_text_id = f"item_btn_text_{i}"
        text_id = f"item_text_{i}"
        
        status_label = "Mark Pending" if item["status"] == "Done" else "Mark Done"
        target_status = "Pending" if item["status"] == "Done" else "Done"
        
        display_label = f"#{item['priority_rank']} [{item['category']}] {item['insight_text']} → {item['action_text']}"
        
        components.extend([
            {
                "id": row_id,
                "component": {
                    "Row": {
                        "children": {
                            "explicitList": [text_id, btn_id]
                        },
                        "distribution": "spaceBetween"
                    }
                }
            },
            {
                "id": text_id,
                "component": {
                    "Text": {
                        "text": {
                            "literalString": display_label
                        }
                    }
                },
                "weight": 5
            },
            {
                "id": btn_id,
                "component": {
                    "Button": {
                        "child": btn_text_id,
                        "action": {
                            "name": "update_action_item_status",
                            "context": [
                                {"key": "action_item_id", "value": {"literalString": item["action_item_id"]}},
                                {"key": "status", "value": {"literalString": target_status}},
                                {"key": "store_id", "value": {"literalString": store_id}},
                                {"key": "date", "value": {"literalString": date}}
                            ]
                        }
                    }
                },
                "weight": 1
            },
            {
                "id": btn_text_id,
                "component": {
                    "Text": {
                        "text": {
                            "literalString": status_label
                        }
                    }
                }
            }
        ])
        
    # Longitudinal Trends using native DataDashboard component
    components.extend([
        {
            "id": "trends_card",
            "component": {
                "Card": {
                    "child": "trends_data_dashboard"
                }
            }
        },
        {
            "id": "trends_data_dashboard",
            "component": {
                "DataDashboard": {
                    "title": "Trailing 10-Day Longitudinal Operational Trends",
                    "subtitle": "Longitudinal telemetry vs operational benchmarks",
                    "sections": [
                        {
                            "type": "stat_cards",
                            "cards": [
                                {
                                    "label": "⏱️ Drive-Thru Speed",
                                    "value": f"{speed_val}s",
                                    "subtitle": f"[ {speed_spark} ]  Target: <300s ({speed_status})"
                                },
                                {
                                    "label": "💸 Labor Cost %",
                                    "value": f"{labor_val}%",
                                    "subtitle": f"[ {labor_spark} ]  Target: <22.0% ({labor_status})"
                                },
                                {
                                    "label": "🎯 Order Accuracy",
                                    "value": f"{accuracy_pct:.2f}%",
                                    "subtitle": f"[ {accuracy_spark} ]  Target: >98.0% ({accuracy_status})"
                                },
                                {
                                    "label": "🗑️ Daily Food Waste",
                                    "value": f"{waste_val} lbs",
                                    "subtitle": f"[ {waste_spark} ]  Target: <15.0 lbs ({waste_status})"
                                }
                            ]
                        }
                    ]
                }
            }
        }
    ])

    ui_json = [
        {
            "beginRendering": {
                "surfaceId": "default",
                "catalogId": "https://a2ui.org/specification/v0_8/standard_catalog_definition.json",
                "root": "dashboard_root",
                "styles": {
                    "primaryColor": "#cc1a1a",
                    "font": "Outfit"
                }
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "default",
                "components": components
            }
        }
    ]

    parts = [Part(root=TextPart(text=md_text))]
    parts.extend([Part(root=DataPart(data=item, metadata={"mimeType": "application/json+a2ui"})) for item in ui_json])

    return {
        "is_task_complete": True,
        "parts": parts
    }

  def _render_store_dashboard_v09(self, store_id: str, date: str) -> dict[str, Any]:
    # Query BigQuery
    metrics = get_store_metrics(store_id, date)
    checklist = get_action_items(store_id, date)
    
    # Get latest metrics for numbers
    latest_metrics = metrics[-1] if metrics else {}
    speed_val = latest_metrics.get("drive_thru_avg_seconds", 0)
    labor_val = latest_metrics.get("labor_cost_percentage", 0.0)
    accuracy_val = latest_metrics.get("order_accuracy_rate", 0.0)
    accuracy_pct = accuracy_val * 100
    waste_val = latest_metrics.get("food_waste_lbs", 0.0)
    
    # Generate sparks
    speed_spark = self._make_sparkline([m.get("drive_thru_avg_seconds", 0) for m in metrics])
    labor_spark = self._make_sparkline([m.get("labor_cost_percentage", 0.0) for m in metrics])
    accuracy_spark = self._make_sparkline([m.get("order_accuracy_rate", 0.0) for m in metrics])
    waste_spark = self._make_sparkline([m.get("food_waste_lbs", 0.0) for m in metrics])
    
    speed_status = "🟢 OPTIMAL" if speed_val < 300 else "🔴 ELEVATED"
    labor_status = "🟢 OPTIMAL" if labor_val < 22.0 else "⚠️ ELEVATED"
    accuracy_status = "🟢 OPTIMAL" if accuracy_pct >= 98.0 else "⚠️ BELOW BENCHMARK"
    waste_status = "🟢 OPTIMAL" if waste_val < 15.0 else "⚠️ ELEVATED"
    
    # Synthesis operational summary
    store_names = {
        "dublin_hq": "Dublin Corporate Headquarters",
        "atlanta_peachtree": "Atlanta Peachtree",
        "costco_campus": "Costco Campus",
        "savannah_riverfront": "Savannah Riverfront",
    }
    store_name = store_names.get(store_id, store_id.replace("_", " ").title())
    
    highlights = []
    if speed_val > 300:
        highlights.append(f"Drive-thru speed is elevated at {speed_val}s (target: <300s).")
    else:
        highlights.append(f"Drive-thru avg speed is excellent at {speed_val}s.")
        
    if labor_val > 22.0:
        highlights.append(f"Labor cost is slightly elevated at {labor_val}% (target: 22%).")
    else:
        highlights.append(f"Labor cost is optimized at {labor_val}%.")
        
    if accuracy_pct < 98.0:
        highlights.append(f"Order accuracy ({accuracy_pct:.2f}%) is below our 98% benchmark.")
    else:
        highlights.append(f"Order accuracy is exceptional at {accuracy_pct:.2f}%.")
        
    summary_text = f"Executive Telemetry Summary: {store_name} on {date}. " + " ".join(highlights)
    md_text = f"📊 Rendering the **{store_name}** dashboard context below:"

    components = []
    
    # Root
    components.append({
        "id": "dashboard_root",
        "component": "Column",
        "children": ["greeting_card", "date_carousel_card", "checklist_card", "trends_card"]
    })
    
    # Greeting Card
    components.extend([
        {
            "id": "greeting_card",
            "component": "Card",
            "child": "greeting_column"
        },
        {
            "id": "greeting_column",
            "component": "Column",
            "children": ["greeting_h1", "greeting_text"]
        },
        {
            "id": "greeting_h1",
            "component": "Text",
            "text": f"QSR - {store_name}",
            "variant": "h1"
        },
        {
            "id": "greeting_text",
            "component": "Text",
            "text": summary_text,
            "variant": "body"
        }
    ])
    
    # Date Carousel Card
    carousel_dates = ["2026-05-24", "2026-05-25", "2026-05-26", "2026-05-27", "2026-05-28"]
    date_btn_ids = [f"date_btn_{d}" for d in carousel_dates]
    
    components.extend([
        {
            "id": "date_carousel_card",
            "component": "Card",
            "child": "date_carousel_column"
        },
        {
            "id": "date_carousel_column",
            "component": "Column",
            "children": ["date_carousel_h2", "date_carousel_row"]
        },
        {
            "id": "date_carousel_h2",
            "component": "Text",
            "text": "Select Date Context (5-Day Rolling History)",
            "variant": "h2"
        },
        {
            "id": "date_carousel_row",
            "component": "Row",
            "children": date_btn_ids,
            "distribution": "spaceEvenly"
        }
    ])
    
    for d in carousel_dates:
        components.extend([
            {
                "id": f"date_btn_{d}",
                "component": "Button",
                "child": f"date_btn_text_{d}",
                "action": {
                    "event": {
                        "name": "get_action_items",
                        "context": {
                            "store_id": store_id,
                            "date": d
                        }
                    }
                }
            },
            {
                "id": f"date_btn_text_{d}",
                "component": "Text",
                "text": d
            }
        ])
        
    # Checklist Card
    done_count = sum(1 for item in checklist if item["status"] == "Done")
    total_count = len(checklist) if checklist else 10
    progress_pct = int(done_count / total_count * 100) if total_count > 0 else 0
    solid_blocks = done_count
    empty_blocks = total_count - done_count
    progress_bar = f"Compliance Progress: [{'█' * solid_blocks}{'░' * empty_blocks}] {progress_pct}% Done ({done_count}/{total_count} items resolved)"
    
    checklist_row_ids = [f"checklist_row_{i}" for i in range(len(checklist))]
    
    components.extend([
        {
            "id": "checklist_card",
            "component": "Card",
            "child": "checklist_column"
        },
        {
            "id": "checklist_column",
            "component": "Column",
            "children": ["checklist_h2", "compliance_progress_text", "checklist_list"]
        },
        {
            "id": "checklist_h2",
            "component": "Text",
            "text": "Top 10 Daily Operational Actions",
            "variant": "h2"
        },
        {
            "id": "compliance_progress_text",
            "component": "Text",
            "text": progress_bar,
            "variant": "body"
        },
        {
            "id": "checklist_list",
            "component": "List",
            "children": checklist_row_ids
        }
    ])
    
    for i, item in enumerate(checklist):
        row_id = f"checklist_row_{i}"
        btn_id = f"item_btn_{i}"
        btn_text_id = f"item_btn_text_{i}"
        text_id = f"item_text_{i}"
        
        status_label = "Mark Pending" if item["status"] == "Done" else "Mark Done"
        target_status = "Pending" if item["status"] == "Done" else "Done"
        
        display_label = f"#{item['priority_rank']} [{item['category']}] {item['insight_text']} → {item['action_text']}"
        
        components.extend([
            {
                "id": row_id,
                "component": "Row",
                "children": [text_id, btn_id],
                "distribution": "spaceBetween"
            },
            {
                "id": text_id,
                "component": "Text",
                "text": display_label,
                "weight": 5
            },
            {
                "id": btn_id,
                "component": "Button",
                "child": btn_text_id,
                "action": {
                    "event": {
                        "name": "update_action_item_status",
                        "context": {
                            "action_item_id": item["action_item_id"],
                            "status": target_status,
                            "store_id": store_id,
                            "date": date
                        }
                    }
                },
                "weight": 1
            },
            {
                "id": btn_text_id,
                "component": "Text",
                "text": status_label
            }
        ])
        
    # Longitudinal Trends using native DataDashboard component
    components.extend([
        {
            "id": "trends_card",
            "component": "Card",
            "child": "trends_data_dashboard"
        },
        {
            "id": "trends_data_dashboard",
            "component": "DataDashboard",
            "title": "Trailing 10-Day Longitudinal Operational Trends",
            "subtitle": "Longitudinal telemetry vs operational benchmarks",
            "sections": [
                {
                    "type": "stat_cards",
                    "cards": [
                        {
                            "label": "⏱️ Drive-Thru Speed",
                            "value": f"{speed_val}s",
                            "subtitle": f"[ {speed_spark} ]  Target: <300s ({speed_status})"
                        },
                        {
                            "label": "💸 Labor Cost %",
                            "value": f"{labor_val}%",
                            "subtitle": f"[ {labor_spark} ]  Target: <22.0% ({labor_status})"
                        },
                        {
                            "label": "🎯 Order Accuracy",
                            "value": f"{accuracy_pct:.2f}%",
                            "subtitle": f"[ {accuracy_spark} ]  Target: >98.0% ({accuracy_status})"
                        },
                        {
                            "label": "🗑️ Daily Food Waste",
                            "value": f"{waste_val} lbs",
                            "subtitle": f"[ {waste_spark} ]  Target: <15.0 lbs ({waste_status})"
                        }
                    ]
                }
            ]
        }
    ])

    ui_json = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "default",
                "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json",
                "root": "dashboard_root",
                "theme": {
                    "primaryColor": "#cc1a1a",
                    "font": "Outfit"
                }
            }
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "default",
                "components": components
            }
        }
    ]

    parts = [Part(root=TextPart(text=md_text))]
    parts.extend([Part(root=DataPart(data=item, metadata={"mimeType": "application/json+a2ui"})) for item in ui_json])

    return {
        "is_task_complete": True,
        "parts": parts
    }

  def _render_metric_dashboard(self, store_id: str, date: str, metric_type: str) -> dict[str, Any]:
    # Query BigQuery
    metrics = get_store_metrics(store_id, date)
    
    store_names = {
        "dublin_hq": "Dublin Corporate Headquarters",
        "atlanta_peachtree": "Atlanta Peachtree",
        "costco_campus": "Costco Campus",
        "savannah_riverfront": "Savannah Riverfront",
    }
    store_name = store_names.get(store_id, store_id.replace("_", " ").title())
    
    # Identify metric properties and chart styling
    metric_label = ""
    metric_key = ""
    chart_color = "#3b82f6"
    y_title = ""
    
    if metric_type == "speed":
      metric_label = "⏱️ Drive-Thru Speed"
      metric_key = "drive_thru_avg_seconds"
      chart_color = "#f59e0b" # Warm Amber
      y_title = "Speed (seconds)"
    elif metric_type == "labor":
      metric_label = "💸 Labor Cost %"
      metric_key = "labor_cost_percentage"
      chart_color = "#a855f7" # Vibrant Purple
      y_title = "Labor Cost %"
    elif metric_type == "accuracy":
      metric_label = "🎯 Order Accuracy"
      metric_key = "order_accuracy_rate"
      chart_color = "#ec4899" # Premium Rose Pink
      y_title = "Accuracy %"
    elif metric_type == "waste":
      metric_label = "🗑️ Daily Food Waste"
      metric_key = "food_waste_lbs"
      chart_color = "#f97316" # Operations Orange
      y_title = "Food Waste (lbs)"
      
    md_text = f"📊 Rendering dedicated **{metric_label}** telemetry table for **{store_name}**:"
    
    # Generate chronological ascending chart dataset
    chart_data = []
    for m in metrics:
      m_date = m.get("date", "")
      date_short = m_date[5:] if len(m_date) >= 10 else m_date
      raw_val = m.get(metric_key, 0.0)
      if metric_type == "accuracy":
        val_to_plot = raw_val * 100
      else:
        val_to_plot = raw_val
      chart_data.append({
          "date_short": date_short,
          "value": round(val_to_plot, 2)
      })

    components = []
    
    # Root Column
    components.append({
        "id": "dashboard_root",
        "component": {
            "Column": {
                "children": {
                    "explicitList": ["greeting_card", "chart_card", "table_card", "navigation_card"]
                }
            }
        }
    })
    
    # Chart Card and VegaChart Component
    components.extend([
        {
            "id": "chart_card",
            "component": {
                "Card": {
                    "child": "chart_column"
                }
            }
        },
        {
            "id": "chart_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["chart_title", "metric_chart"]
                    }
                }
            }
        },
        {
            "id": "chart_title",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"10-Day Historical Trend Analysis - {metric_label}"
                    },
                    "usageHint": "h2"
                }
            }
        },
        {
            "id": "metric_chart",
            "component": {
                "VegaChart": {
                    "spec": {
                        "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                        "description": f"Historical 10-day line chart trend for {metric_label}",
                        "width": "container",
                        "height": 220,
                        "data": { "values": chart_data },
                        "mark": {
                            "type": "line",
                            "color": chart_color,
                            "point": { "color": chart_color, "size": 60 },
                            "strokeWidth": 3
                        },
                        "encoding": {
                            "x": {
                                "field": "date_short",
                                "type": "ordinal",
                                "axis": { "title": "Date", "labelAngle": 0 }
                            },
                            "y": {
                                "field": "value",
                                "type": "quantitative",
                                "scale": { "zero": False },
                                "axis": { "title": y_title }
                            },
                            "tooltip": [
                                {"field": "date_short", "type": "ordinal", "title": "Date"},
                                {"field": "value", "type": "quantitative", "title": y_title}
                            ]
                        }
                    }
                }
            }
        }
    ])
    
    # Greeting Card
    components.extend([
        {
            "id": "greeting_card",
            "component": {
                "Card": {
                    "child": "greeting_column"
                }
            }
        },
        {
            "id": "greeting_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["greeting_h1", "greeting_text"]
                    }
                }
            }
        },
        {
            "id": "greeting_h1",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"{store_name} - Telemetry"
                    },
                    "usageHint": "h1"
                }
            }
        },
        {
            "id": "greeting_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"Dedicated telemetry dashboard displaying historical trend analysis for {metric_label}."
                    }
                }
            }
        }
    ])
    
    # Table Card
    table_children = ["table_h2", "table_header_row"]
    
    # Add header Row
    components.extend([
        {
            "id": "table_header_row",
            "component": {
                "Row": {
                    "children": {
                        "explicitList": ["th_date", "th_value", "th_target", "th_status"]
                    },
                    "distribution": "spaceBetween"
                }
            }
        },
        {
            "id": "th_date",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Date"
                    }
                }
            },
            "weight": 2
        },
        {
            "id": "th_value",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Value"
                    }
                }
            },
            "weight": 2
        },
        {
            "id": "th_target",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Target"
                    }
                }
            },
            "weight": 2
        },
        {
            "id": "th_status",
            "component": {
                "Text": {
                    "text": {
                        "literalString": "Status"
                    }
                }
            },
            "weight": 2
        }
    ])
    
    # Reverse metrics so they are in descending order (newest first)
    for idx, m in enumerate(reversed(metrics)):
      row_id = f"table_row_{idx}"
      table_children.append(row_id)
      
      m_date = m.get("date", "")
      raw_val = m.get(metric_key, 0.0)
      
      val_str = ""
      target_str = ""
      status_str = ""
      
      if metric_type == "speed":
        val_str = f"{raw_val}s"
        target_str = "<300s"
        status_str = "🟢 OPTIMAL" if raw_val < 300 else "🔴 ELEVATED"
      elif metric_type == "labor":
        val_str = f"{raw_val}%"
        target_str = "<22.0%"
        status_str = "🟢 OPTIMAL" if raw_val < 22.0 else "⚠️ ELEVATED"
      elif metric_type == "accuracy":
        accuracy_pct = raw_val * 100
        val_str = f"{accuracy_pct:.2f}%"
        target_str = ">98.0%"
        status_str = "🟢 OPTIMAL" if accuracy_pct >= 98.0 else "⚠️ BELOW BENCHMARK"
      elif metric_type == "waste":
        val_str = f"{raw_val} lbs"
        target_str = "<15.0 lbs"
        status_str = "🟢 OPTIMAL" if raw_val < 15.0 else "⚠️ ELEVATED"
        
      cell_date_id = f"cell_date_{idx}"
      cell_val_id = f"cell_val_{idx}"
      cell_target_id = f"cell_target_{idx}"
      cell_status_id = f"cell_status_{idx}"
      
      components.extend([
          {
              "id": row_id,
              "component": {
                  "Row": {
                      "children": {
                          "explicitList": [cell_date_id, cell_val_id, cell_target_id, cell_status_id]
                      },
                      "distribution": "spaceBetween"
                  }
              }
          },
          {
              "id": cell_date_id,
              "component": {
                  "Text": {
                      "text": {
                          "literalString": m_date
                      }
                  }
              },
              "weight": 2
          },
          {
              "id": cell_val_id,
              "component": {
                  "Text": {
                      "text": {
                          "literalString": val_str
                      }
                  }
              },
              "weight": 2
          },
          {
              "id": cell_target_id,
              "component": {
                  "Text": {
                      "text": {
                          "literalString": target_str
                      }
                  }
              },
              "weight": 2
          },
          {
              "id": cell_status_id,
              "component": {
                  "Text": {
                      "text": {
                          "literalString": status_str
                      }
                  }
              },
              "weight": 2
          }
      ])
      
    components.extend([
        {
            "id": "table_card",
            "component": {
                "Card": {
                    "child": "table_column"
                }
            }
        },
        {
            "id": "table_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": table_children
                    }
                }
            }
        },
        {
            "id": "table_h2",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"Trailing 10-Day Telemetry Breakdown - {metric_label}"
                    },
                    "usageHint": "h2"
                }
            }
        }
    ])
    
    # Navigation Card
    components.extend([
        {
            "id": "navigation_card",
            "component": {
                "Card": {
                    "child": "navigation_column"
                }
            }
        },
        {
            "id": "navigation_column",
            "component": {
                "Column": {
                    "children": {
                        "explicitList": ["navigation_btn"]
                    }
                }
            }
        },
        {
            "id": "navigation_btn",
            "component": {
                "Button": {
                    "child": "navigation_btn_text",
                    "action": {
                        "name": "get_action_items",
                        "context": [
                            {"key": "store_id", "value": {"literalString": store_id}},
                            {"key": "date", "value": {"literalString": date}}
                        ]
                    }
                }
            }
        },
        {
            "id": "navigation_btn_text",
            "component": {
                "Text": {
                    "text": {
                        "literalString": f"View Full Operational Checklist & Trends Dashboard for {store_name}"
                    }
                }
            }
        }
    ])
    
    ui_json = [
        {
            "beginRendering": {
                "surfaceId": "default",
                "catalogId": "https://a2ui.org/specification/v0_8/standard_catalog_definition.json",
                "root": "dashboard_root",
                "styles": {
                    "primaryColor": "#cc1a1a",
                    "font": "Outfit"
                }
            }
        },
        {
            "surfaceUpdate": {
                "surfaceId": "default",
                "components": components
            }
        }
    ]
    
    parts = [Part(root=TextPart(text=md_text))]
    parts.extend([Part(root=DataPart(data=item, metadata={"mimeType": "application/json+a2ui"})) for item in ui_json])
    
    return {
        "is_task_complete": True,
        "parts": parts
    }

  def _render_metric_dashboard_v09(self, store_id: str, date: str, metric_type: str) -> dict[str, Any]:
    # Query BigQuery
    metrics = get_store_metrics(store_id, date)
    
    store_names = {
        "dublin_hq": "Dublin Corporate Headquarters",
        "atlanta_peachtree": "Atlanta Peachtree",
        "costco_campus": "Costco Campus",
        "savannah_riverfront": "Savannah Riverfront",
    }
    store_name = store_names.get(store_id, store_id.replace("_", " ").title())
    
    # Identify metric properties and chart styling
    metric_label = ""
    metric_key = ""
    chart_color = "#3b82f6"
    y_title = ""
    
    if metric_type == "speed":
      metric_label = "⏱️ Drive-Thru Speed"
      metric_key = "drive_thru_avg_seconds"
      chart_color = "#f59e0b" # Warm Amber
      y_title = "Speed (seconds)"
    elif metric_type == "labor":
      metric_label = "💸 Labor Cost %"
      metric_key = "labor_cost_percentage"
      chart_color = "#a855f7" # Vibrant Purple
      y_title = "Labor Cost %"
    elif metric_type == "accuracy":
      metric_label = "🎯 Order Accuracy"
      metric_key = "order_accuracy_rate"
      chart_color = "#ec4899" # Premium Rose Pink
      y_title = "Accuracy %"
    elif metric_type == "waste":
      metric_label = "🗑️ Daily Food Waste"
      metric_key = "food_waste_lbs"
      chart_color = "#f97316" # Operations Orange
      y_title = "Food Waste (lbs)"
      
    md_text = f"📊 Rendering dedicated **{metric_label}** telemetry table for **{store_name}**:"
    
    # Generate chronological ascending chart dataset
    chart_data = []
    for m in metrics:
      m_date = m.get("date", "")
      date_short = m_date[5:] if len(m_date) >= 10 else m_date
      raw_val = m.get(metric_key, 0.0)
      if metric_type == "accuracy":
        val_to_plot = raw_val * 100
      else:
        val_to_plot = raw_val
      chart_data.append({
          "date_short": date_short,
          "value": round(val_to_plot, 2)
      })

    components = []
    
    # Root Column
    components.append({
        "id": "dashboard_root",
        "component": "Column",
        "children": ["greeting_card", "chart_card", "table_card", "navigation_card"]
    })
    
    # Chart Card and VegaChart Component (v0.9 Flattened Layout)
    components.extend([
        {
            "id": "chart_card",
            "component": "Card",
            "child": "chart_column"
        },
        {
            "id": "chart_column",
            "component": "Column",
            "children": ["chart_title", "metric_chart"]
        },
        {
            "id": "chart_title",
            "component": "Text",
            "text": f"10-Day Historical Trend Analysis - {metric_label}",
            "variant": "h2"
        },
        {
            "id": "metric_chart",
            "component": "VegaChart",
            "spec": {
                "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
                "description": f"Historical 10-day line chart trend for {metric_label}",
                "width": "container",
                "height": 220,
                "data": { "values": chart_data },
                "mark": {
                    "type": "line",
                    "color": chart_color,
                    "point": { "color": chart_color, "size": 60 },
                    "strokeWidth": 3
                },
                "encoding": {
                    "x": {
                        "field": "date_short",
                        "type": "ordinal",
                        "axis": { "title": "Date", "labelAngle": 0 }
                    },
                    "y": {
                        "field": "value",
                        "type": "quantitative",
                        "scale": { "zero": False },
                        "axis": { "title": y_title }
                    },
                    "tooltip": [
                        {"field": "date_short", "type": "ordinal", "title": "Date"},
                        {"field": "value", "type": "quantitative", "title": y_title}
                    ]
                }
            }
        }
    ])
    
    # Greeting Card
    components.extend([
        {
            "id": "greeting_card",
            "component": "Card",
            "child": "greeting_column"
        },
        {
            "id": "greeting_column",
            "component": "Column",
            "children": ["greeting_h1", "greeting_text"]
        },
        {
            "id": "greeting_h1",
            "component": "Text",
            "text": f"{store_name} - Telemetry",
            "variant": "h1"
        },
        {
            "id": "greeting_text",
            "component": "Text",
            "text": f"Dedicated telemetry dashboard displaying historical trend analysis for {metric_label}.",
            "variant": "body"
        }
    ])
    
    # Table Card
    table_children = ["table_h2", "table_header_row"]
    
    # Add header Row
    components.extend([
        {
            "id": "table_header_row",
            "component": "Row",
            "children": ["th_date", "th_value", "th_target", "th_status"],
            "distribution": "spaceBetween"
        },
        {
            "id": "th_date",
            "component": "Text",
            "text": "Date"
        },
        {
            "id": "th_value",
            "component": "Text",
            "text": "Value"
        },
        {
            "id": "th_target",
            "component": "Text",
            "text": "Target"
        },
        {
            "id": "th_status",
            "component": "Text",
            "text": "Status"
        }
    ])
    
    # Reverse metrics for descending order
    for idx, m in enumerate(reversed(metrics)):
      row_id = f"table_row_{idx}"
      table_children.append(row_id)
      
      m_date = m.get("date", "")
      raw_val = m.get(metric_key, 0.0)
      
      val_str = ""
      target_str = ""
      status_str = ""
      
      if metric_type == "speed":
        val_str = f"{raw_val}s"
        target_str = "<300s"
        status_str = "🟢 OPTIMAL" if raw_val < 300 else "🔴 ELEVATED"
      elif metric_type == "labor":
        val_str = f"{raw_val}%"
        target_str = "<22.0%"
        status_str = "🟢 OPTIMAL" if raw_val < 22.0 else "⚠️ ELEVATED"
      elif metric_type == "accuracy":
        accuracy_pct = raw_val * 100
        val_str = f"{accuracy_pct:.2f}%"
        target_str = ">98.0%"
        status_str = "🟢 OPTIMAL" if accuracy_pct >= 98.0 else "⚠️ BELOW BENCHMARK"
      elif metric_type == "waste":
        val_str = f"{raw_val} lbs"
        target_str = "<15.0 lbs"
        status_str = "🟢 OPTIMAL" if raw_val < 15.0 else "⚠️ ELEVATED"
        
      cell_date_id = f"cell_date_{idx}"
      cell_val_id = f"cell_val_{idx}"
      cell_target_id = f"cell_target_{idx}"
      cell_status_id = f"cell_status_{idx}"
      
      components.extend([
          {
              "id": row_id,
              "component": "Row",
              "children": [cell_date_id, cell_val_id, cell_target_id, cell_status_id],
              "distribution": "spaceBetween"
          },
          {
              "id": cell_date_id,
              "component": "Text",
              "text": m_date
          },
          {
              "id": cell_val_id,
              "component": "Text",
              "text": val_str
          },
          {
              "id": cell_target_id,
              "component": "Text",
              "text": target_str
          },
          {
              "id": cell_status_id,
              "component": "Text",
              "text": status_str
          }
      ])
      
    components.extend([
        {
            "id": "table_card",
            "component": "Card",
            "child": "table_column"
        },
        {
            "id": "table_column",
            "component": "Column",
            "children": table_children
        },
        {
            "id": "table_h2",
            "component": "Text",
            "text": f"Trailing 10-Day Telemetry Breakdown - {metric_label}",
            "variant": "h2"
        }
    ])
    
    # Navigation Card
    components.extend([
        {
            "id": "navigation_card",
            "component": "Card",
            "child": "navigation_column"
        },
        {
            "id": "navigation_column",
            "component": "Column",
            "children": ["navigation_btn"]
        },
        {
            "id": "navigation_btn",
            "component": "Button",
            "child": "navigation_btn_text",
            "action": {
                "event": {
                    "name": "get_action_items",
                    "context": {
                        "store_id": store_id,
                        "date": date
                    }
                }
            }
        },
        {
            "id": "navigation_btn_text",
            "component": "Text",
            "text": f"View Full Operational Checklist & Trends Dashboard for {store_name}",
            "variant": "body"
        }
    ])
    
    ui_json = [
        {
            "version": "v0.9",
            "createSurface": {
                "surfaceId": "default",
                "catalogId": "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json",
                "root": "dashboard_root",
                "theme": {
                    "primaryColor": "#cc1a1a",
                    "font": "Outfit"
                }
            }
        },
        {
            "version": "v0.9",
            "updateComponents": {
                "surfaceId": "default",
                "components": components
            }
        }
    ]
    
    parts = [Part(root=TextPart(text=md_text))]
    parts.extend([Part(root=DataPart(data=item, metadata={"mimeType": "application/json+a2ui"})) for item in ui_json])
    
    return {
        "is_task_complete": True,
        "parts": parts
    }

  async def stream(
      self,
      query: str,
      session_id: str,
      ui_version: Optional[str] = None,
      use_streaming: bool = True,
      supported_catalogs: Optional[list[str]] = None,
  ) -> AsyncIterable[dict[str, Any]]:
    """Stateful stream generator executing ADK agent queries and yielding A2A compliant Part structures."""
    from google.adk import Runner
    from google.genai import types
    import json

    logger.info(f"QSRAgent.stream received query='{query}', ui_version={ui_version} for session={session_id}")

    try:
      # Normalize query
      q = query.strip().lower()
      
      # 1. Detect greetings and welcome requests
      greeting_patterns = [
          r"^\s*hi\s*$",
          r"^\s*hello\s*$",
          r"^\s*hey\s*$",
          r"^\s*greetings\s*$",
          r"^\s*yo\s*$",
          r"^\s*howdy\s*$",
          r"^\s*hi\s+there\s*$",
          r"^\s*hello\s+there\s*$",
      ]
      is_greeting = any(re.match(pattern, q) for pattern in greeting_patterns)
      if is_greeting or q in ["home", "back", "welcome", "landing", "hi dies silently"]:
        if ui_version == "0.9":
          yield self._render_welcome_dashboard_v09()
        else:
          yield self._render_welcome_dashboard()
        return

      # 2. Detect status update requests
      update_match = re.search(r"update\s+compliance\s+status\s+of\s+action\s+item\s+(\S+)\s+to\s+(\S+)", q)
      if update_match:
        action_item_id = update_match.group(1).rstrip(".")
        status = update_match.group(2).rstrip(".")
        status_capitalized = "Done" if "done" in status.lower() else "Pending"
        
        logger.info(f"Executing status update for action_item_id='{action_item_id}' to '{status_capitalized}'")
        
        # Look up context of action item from BigQuery
        store_id, date = get_action_item_context(action_item_id)
        
        # Run status write-back to BigQuery
        update_action_item_status(action_item_id, status_capitalized)
        
        # Render refreshed store dashboard
        if ui_version == "0.9":
          yield self._render_store_dashboard_v09(store_id, date)
        else:
          yield self._render_store_dashboard(store_id, date)
        return

      # 3. Detect store dashboard requests & specific metrics
      store_id = None
      is_conversational_meta = any(re.search(pat, q) for pat in [
          r"\bwhy\b", r"\bhow\b", r"\bexplain\b", r"\bwhat is\b", r"\bwhat does\b",
          r"\bif i\b", r"\bif you\b", r"\bcan you\b", r"\bcould you\b", r"\bquestion\b",
          r"\bunderstand\b"
      ])
      
      target_metric = None
      if not is_conversational_meta:
        for s in ["dublin_hq", "costco_campus", "atlanta_peachtree", "savannah_riverfront"]:
          if s in q or s.replace("_", " ") in q or s.split("_")[0] in q:
            store_id = s
            break
            
        # Detect if the query is asking about a specific metric
        metric_keywords = {
            "speed": ["speed", "drive", "thru", "service"],
            "labor": ["labor", "payroll", "cost"],
            "accuracy": ["accuracy", "order"],
            "waste": ["waste", "food"]
        }
        
        for m_type, kws in metric_keywords.items():
          if any(kw in q for kw in kws) or (m_type == "speed" and any(emoji in q for emoji in ["⏱️"])) or (m_type == "labor" and any(emoji in q for emoji in ["💸"])) or (m_type == "accuracy" and any(emoji in q for emoji in ["🎯"])) or (m_type == "waste" and any(emoji in q for emoji in ["🗑️"])):
            target_metric = m_type
            break
            
        # If they are asking about a metric or checklist/compliance, but no store_id was matched, default to dublin_hq
        if not store_id:
          has_metric_intent = (target_metric is not None) or any(kw in q for kw in ["kpi", "metric", "trend", "telemetry", "dashboard", "table", "data", "checklist", "compliance"])
          if has_metric_intent:
            store_id = "dublin_hq"
            logger.info(f"Analytical metric intent detected in query '{query}' without store_id. Defaulting to fallback store='{store_id}'")

      if store_id:
        # Extract date or default
        date = "2026-05-28"
        date_match = re.search(r"\b(2026-\d{2}-\d{2})\b", q)
        if date_match:
          date = date_match.group(1)
          
        if target_metric:
          logger.info(f"Rendering dedicated metric dashboard for store_id='{store_id}', date='{date}', metric='{target_metric}', ui_version={ui_version}")
          if ui_version == "0.9":
            yield self._render_metric_dashboard_v09(store_id, date, target_metric)
          else:
            yield self._render_metric_dashboard(store_id, date, target_metric)
        else:
          logger.info(f"Rendering full store dashboard for store_id='{store_id}', date='{date}', ui_version={ui_version}")
          if ui_version == "0.9":
            yield self._render_store_dashboard_v09(store_id, date)
          else:
            yield self._render_store_dashboard(store_id, date)
        return

      # 4. Fallback: Conversational query using ADK Runner
      try:
        session = await self._session_service.get_session(
            app_name="QSRDashboard", session_id=session_id, user_id="operator_123"
        )
        if session is None:
          session = await self._session_service.create_session(
              app_name="QSRDashboard", session_id=session_id, user_id="operator_123"
          )
      except Exception as ex:
        logger.warning(f"Error checking session, attempting fallback: {ex}")
        try:
          session = await self._session_service.create_session(
              app_name="QSRDashboard", session_id=session_id, user_id="operator_123"
          )
        except Exception as fallback_ex:
          logger.warning(f"Fallback session creation failed: {fallback_ex}")
          session = await self._session_service.get_session(
              app_name="QSRDashboard", session_id=session_id, user_id="operator_123"
          )

      user_message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
      accumulated_parts = []
      suppress_text_streaming = False

      async with Runner(
          agent=root_agent,
          app_name="QSRDashboard",
          session_service=self._session_service,
          auto_create_session=True,
      ) as runner:
        for event in runner.run(
            user_id="operator_123",
            session_id=session_id,
            new_message=user_message,
        ):
          if event.content and event.content.parts:
            for part in event.content.parts:
              if part.text:
                text_content = part.text
                
                if not suppress_text_streaming:
                  stripped = text_content.strip()
                  if stripped.startswith("[") or stripped.startswith("{") or stripped.startswith("```"):
                    suppress_text_streaming = True
                
                if suppress_text_streaming:
                  is_friendly_greeting = (
                      text_content.strip().startswith("👋") or 
                      text_content.strip().startswith("📊")
                  )
                  if not is_friendly_greeting:
                    logger.debug("Suppressing streaming raw JSON text chunk: %r", text_content)
                    continue
                
                new_part = Part(root=TextPart(text=text_content))
                accumulated_parts.append(new_part)
                yield {
                    "is_task_complete": False,
                    "parts": [new_part],
                }
              elif part.inline_data:
                try:
                  payload = part.inline_data.data.decode("utf-8")
                  clean_payload = payload.replace("<a2a_datapart_json>", "").replace("</a2a_datapart_json>", "")
                  parsed_json = json.loads(clean_payload)
                  if isinstance(parsed_json, dict) and "data" in parsed_json:
                    new_part = Part(root=DataPart(data=parsed_json["data"], metadata={"mimeType": "application/json+a2ui"}))
                    accumulated_parts.append(new_part)
                    yield {
                        "is_task_complete": False,
                        "parts": [new_part],
                    }
                except Exception as ex:
                  logger.error(f"Error parsing inline_data in stream: {ex}")

      yield {
          "is_task_complete": True,
          "parts": accumulated_parts,
      }

    except Exception as e:
      logger.exception(f"Error during agent stream: {e}")
      yield {
          "is_task_complete": True,
          "parts": [Part(root=TextPart(text=f"An error occurred: {str(e)}"))],
      }
