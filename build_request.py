import json
import sys

service_url = sys.argv[1]
agent_display_name = sys.argv[2]
agent_description = sys.argv[3]

agent_card = {
    "protocolVersion": "0.3.0",
    "name": agent_display_name,
    "description": agent_description,
    "url": service_url,
    "version": "1.0.0",
    "capabilities": {
        "streaming": True,
        "preferredTransport": "JSONRPC",
        "extensions": [
            {
                "uri": "https://a2ui.org/a2a-extension/a2ui/v0.8",
                "description": "Provides agent driven UI using the A2UI JSON format.",
                "required": False,
                "params": {
                    "acceptsInlineCatalogs": True,
                    "supportedCatalogIds": [
                        "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
                    ]
                }
            },
            {
                "uri": "https://a2ui.org/a2a-extension/a2ui/v0.9",
                "description": "Provides agent driven UI using the A2UI JSON format.",
                "required": False,
                "params": {
                    "acceptsInlineCatalogs": True,
                    "supportedCatalogIds": [
                        "https://a2ui.org/specification/v0_9/catalogs/basic/catalog.json"
                    ]
                }
            }
        ]
    },
    "skills": [
        {
            "id": "qsr_dashboard",
            "name": "QSR Insights Dashboard",
            "description": "Provides executive dashboard analytics, checklist management, and compliance actions.",
            "tags": ["dashboard", "operational", "compliance", "analytics"],
            "examples": ["Show me the dashboard for dublin_hq", "Update compliance status of item 1"]
        }
    ],
    "defaultInputModes": ["text", "text/plain"],
    "defaultOutputModes": ["text", "text/plain"]
}

payload = {
    "displayName": agent_display_name,
    "description": agent_description,
    "a2aAgentDefinition": {
        "jsonAgentCard": json.dumps(agent_card)
    }
}

with open("agent_request.json", "w") as f:
    json.dump(payload, f, indent=2)
