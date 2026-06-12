#!/bin/bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

set -e

# --- Configuration ---
PROJECT_ID="vertexsearch-447722"
PROJECT_NUMBER="36841365232"
SERVICE_NAME="qsrs-insights-dashboard"
REGION="us-central1"
LOCATION="global"
ENGINE_ID="qsr-s_1778542370208"
AGENT_ID="qsrs-dashboard-agent"

AGENT_DISPLAY_NAME="QSR Insights Dashboard"
AGENT_DESCRIPTION="QSR Insights to Action Agent Dashboard providing executive management, compliance tracking, and longitudinal analytics."

echo "=========================================================="
echo "🚀 DEPLOYING WENDY'S INSIGHTS DASHBOARD TO CLOUD RUN 🚀"
echo "=========================================================="
echo "Project ID:      $PROJECT_ID"
echo "Project Number:  $PROJECT_NUMBER"
echo "Service Name:    $SERVICE_NAME"
echo "Region:          $REGION"
echo "Engine ID:       $ENGINE_ID"
echo "Agent ID:        $AGENT_ID"
echo "=========================================================="

# 1. Load environment variables from .env if present
if [ -f .env ]; then
  echo "Loading environment variables from .env..."
  export $(grep -v '^#' .env | xargs)
fi

# 2. Deploy to Cloud Run from source code
echo "Starting Cloud Run deployment..."
gcloud run deploy "$SERVICE_NAME" \
  --source . \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --memory "1Gi" \
  --allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT="$PROJECT_ID",GOOGLE_CLOUD_LOCATION="$REGION",GOOGLE_GENAI_USE_VERTEXAI=TRUE,MODEL="gemini-2.5-flash",GOOGLE_PYTHON_PACKAGE_MANAGER=uv

# 3. Get the deployed Service URL
echo "Retrieving service URL..."
SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_NUMBER}.${REGION}.run.app"

echo "Service URL is: $SERVICE_URL"

# 4. Update the service to set AGENT_URL environment variable
echo "Updating service with AGENT_URL..."
gcloud run services update "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --update-env-vars=AGENT_URL="$SERVICE_URL"

# 5. Bind Cloud Run IAM Invoker role for Discovery Engine service agent
echo "Assigning roles/run.invoker to Discovery Engine service account..."
gcloud run services add-iam-policy-binding "$SERVICE_NAME" \
  --project="$PROJECT_ID" \
  --region="$REGION" \
  --member="serviceAccount:service-${PROJECT_NUMBER}@gcp-sa-discoveryengine.iam.gserviceaccount.com" \
  --role="roles/run.invoker"

# 6. Register the agent card on Gemini Enterprise Discovery Engine
echo "Preparing registration payload using Python..."
cat << 'EOF' > build_request.py
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
EOF

python3 build_request.py "$SERVICE_URL" "$AGENT_DISPLAY_NAME" "$AGENT_DESCRIPTION"

echo "Registering agent on Gemini Enterprise..."
RESPONSE=$(curl -s -o /tmp/resp.json -w "%{http_code}" -X POST \
  -H "Authorization: Bearer $(gcloud auth print-access-token)" \
  -H "X-Goog-User-Project: ${PROJECT_ID}" \
  -H "Content-Type: application/json" \
  "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_NUMBER}/locations/${LOCATION}/collections/default_collection/engines/${ENGINE_ID}/assistants/default_assistant/agents?agentId=${AGENT_ID}" \
  -d @agent_request.json)

if [ "$RESPONSE" = "409" ] || grep -q "ALREADY_EXISTS" /tmp/resp.json; then
  echo "Agent already exists (409). Updating agent with PATCH..."
  curl -s -X PATCH \
    -H "Authorization: Bearer $(gcloud auth print-access-token)" \
    -H "X-Goog-User-Project: ${PROJECT_ID}" \
    -H "Content-Type: application/json" \
    "https://discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_NUMBER}/locations/${LOCATION}/collections/default_collection/engines/${ENGINE_ID}/assistants/default_assistant/agents/${AGENT_ID}?updateMask=displayName,description,a2aAgentDefinition" \
    -d @agent_request.json
else
  cat /tmp/resp.json
fi

echo ""
echo "=========================================================="
echo "🎉 DEPLOYMENT & REGISTRATION COMPLETE! 🎉"
echo "Agent URL: $SERVICE_URL"
echo "=========================================================="
