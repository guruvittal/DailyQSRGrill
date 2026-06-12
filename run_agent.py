#!/usr/bin/env python3
"""
QSR Insights to Action Agent Dashboard - CLI Test Harness
Provides interactive and programmatic validation of the QSRAgent with BigQuery tools
and v0.8 Lit-friendly A2UI components.
"""

import os
# Configure environment variables to use Vertex AI with target project credentials
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "1"
os.environ["GOOGLE_CLOUD_PROJECT"] = "vertexsearch-447722"
os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

import sys
import asyncio
import argparse
from google.adk import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# Add local path to import
from agent import root_agent

async def run_query(query: str):
    """Run a single query against the QSR ADK agent and print output."""
    session_service = InMemorySessionService()
    
    # Initialize the runner
    async with Runner(
        agent=root_agent, 
        app_name="QSRDashboard",
        session_service=session_service, 
        auto_create_session=True
    ) as runner:
        # Create a new session
        session = await runner.session_service.create_session(app_name="QSRDashboard", user_id="operator_123")
        
        print(f"==================================================")
        print(f"User Request: {query}")
        print(f"==================================================")
        
        # Build the user message content
        user_message = types.Content(role="user", parts=[types.Part.from_text(text=query)])
        
        print("🤖 Invoking Agent via ADK Runner...")
        print("--------------------------------------------------")
        
        response_text = ""
        a2ui_parts = []
        
        # Run agent synchronously using the standard Runner.run generator
        for event in runner.run(
            user_id="operator_123",
            session_id=session.id,
            new_message=user_message
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        response_text += part.text
                        print(part.text, end="", flush=True)
                    elif part.inline_data:
                        a2ui_parts.append(part.inline_data)
        
        print()
        print("--------------------------------------------------")
        
        if a2ui_parts:
            print(f"\n✨ Intercepted {len(a2ui_parts)} Gemini Enterprise A2UI Inline Binary Parts:")
            for idx, data_part in enumerate(a2ui_parts):
                try:
                    payload = data_part.data.decode("utf-8")
                    # Strip delimiters for printing
                    clean_payload = payload.replace("<a2a_datapart_json>", "").replace("</a2a_datapart_json>", "")
                    import json
                    parsed_json = json.loads(clean_payload)
                    print(f"\nPart {idx+1} (MimeType: {data_part.mime_type}):")
                    print(json.dumps(parsed_json, indent=2))
                except Exception as e:
                    print(f"Error printing data part {idx+1}: {e}")
                    print(f"Raw blob: {data_part.data[:200]}...")
        else:
            print("\n⚠️ No A2UI parts returned. Ensure your request targets a specific store (e.g. dublin_hq, atlanta_peachtree).")
            
        print(f"==================================================\n")

async def main():
    parser = argparse.ArgumentParser(description="QSR Insights-to-Action Agent CLI Harness")
    parser.add_argument("query", nargs="?", help="Optional user query to run single-turn")
    parser.add_argument("--interactive", "-i", action="store_true", help="Run in interactive mode")
    args = parser.parse_args()

    # Pre-populate default query if none is provided
    query = args.query
    if not query and not args.interactive:
        query = "Show me the dashboard for dublin_hq on 2026-05-28"

    if args.interactive:
        print("🚀 Starting QSR Agent Interactive Shell. Type 'exit' to quit.")
        print("Available Stores: dublin_hq, costco_campus, atlanta_peachtree, savannah_riverfront\n")
        while True:
            try:
                user_input = input("QSR Op> ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit", "q"]:
                    break
                await run_query(user_input)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
    else:
        await run_query(query)

if __name__ == "__main__":
    asyncio.run(main())
