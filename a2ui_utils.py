import json
import re
from google.genai import types
from google.adk.agents.callback_context import CallbackContext
from google.adk.models.llm_response import LlmResponse

_response_cache = {}

def _wrap_a2ui_part(a2ui_message: dict) -> types.Part:
    """Wrap a single A2UI message for rendering in Gemini Enterprise Lit UI.
    
    Uses binary inline data parts with <a2a_datapart_json> delimiters which are 
    intercepted and rendered natively by the frontend engine.
    """
    datapart_json = json.dumps({
        "kind": "data",
        "metadata": {"mimeType": "application/json+a2ui"},
        "data": a2ui_message,
    })
    blob_data = (
        b"<a2a_datapart_json>"
        + datapart_json.encode("utf-8")
        + b"</a2a_datapart_json>"
    )
    # MUST be an inline_data blob for the built-in frontend interceptor to catch it!
    return types.Part(
        inline_data=types.Blob(
            data=blob_data,
            mime_type="text/plain",
        )
    )

def _extract_friendly_greeting(a2ui_messages: list) -> str:
    """Extracts a prominent title or greeting from the A2UI layout to show as chat text."""
    for msg in a2ui_messages:
        if "surfaceUpdate" in msg and "components" in msg["surfaceUpdate"]:
            components = msg["surfaceUpdate"]["components"]
            for comp_wrapper in components:
                comp = comp_wrapper.get("component", {})
                if "Text" in comp:
                    text_comp = comp["Text"]
                    # h1 represents our dashboard's main landing title
                    if text_comp.get("usageHint") == "h1":
                        title = text_comp.get("text", {}).get("literalString", "")
                        if title:
                            return f"👋 Welcome Operator! Rendering the **{title}** interface below:"
                    # h2 represents sub-dashboards or specific context panels
                    elif text_comp.get("usageHint") == "h2":
                        title = text_comp.get("text", {}).get("literalString", "")
                        if title and "Select" not in title:
                            return f"📊 Rendering the **{title}** dashboard context below:"
    return "📊 Rendering the interactive QSR Insights-to-Action executive dashboard below:"

def a2ui_callback(
    callback_context: CallbackContext,
    llm_response: LlmResponse,
) -> LlmResponse:
    """Convert A2UI JSON array in text output to rendered inline binary components."""
    if not llm_response.content or not llm_response.content.parts:
        return llm_response
        
    for part in llm_response.content.parts:
        if not part.text:
            continue
        text = part.text.strip()
        if not text:
            continue
            
        # Extract json safely regardless of surrounding text
        match = re.search(r'(\{.*\}|\[.*\])', text, re.DOTALL)
        if not match:
            continue
            
        json_text = match.group(1).strip()
        
        # Repair any key-hallucination line fragments (e.g. `"Te`)
        lines = json_text.splitlines()
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"') and not any(stripped.endswith(c) for c in [':', ',', '{', '[', '}', ']']):
                quotes = stripped.count('"')
                if quotes == 1 or (quotes == 2 and ':' not in stripped):
                    continue
            cleaned_lines.append(line)
        json_text = "\n".join(cleaned_lines)
        
        try:
            parsed = json.loads(json_text)
        except json.JSONDecodeError:
            try:
                fixed = "[" + re.sub(r'\}\s*\{', '},{', json_text) + "]"
                parsed = json.loads(fixed)
            except json.JSONDecodeError:
                continue

        if not isinstance(parsed, list):
            parsed = [parsed]

        a2ui_keys = {"beginRendering", "surfaceUpdate", "dataModelUpdate", "deleteSurface"}
        a2ui_messages = []
        
        for msg in parsed:
            if not isinstance(msg, dict):
                continue
            target = msg["data"] if ("data" in msg and isinstance(msg["data"], dict)) else msg
            if any(k in target for k in a2ui_keys):
                a2ui_messages.append(target)

        if not a2ui_messages:
            continue

        new_parts = []
        # Prepend a beautiful plain-text greeting part so that the chat bubble is never empty!
        friendly_text = _extract_friendly_greeting(a2ui_messages)
        new_parts.append(types.Part(text=friendly_text))
        
        # Append the binary wrapped A2UI parts
        new_parts.extend([_wrap_a2ui_part(m) for m in a2ui_messages])
        
        return LlmResponse(
            content=types.Content(role="model", parts=new_parts),
            custom_metadata={"a2a:response": "true"},
        )
        
    return llm_response
