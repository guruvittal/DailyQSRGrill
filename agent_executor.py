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

import logging

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import (
    DataPart,
    Part,
    Task,
    TaskState,
    TextPart,
    UnsupportedOperationError,
)
from a2a.utils import (
    new_agent_parts_message,
    new_agent_text_message,
    new_task,
)
from a2a.utils.errors import ServerError
from a2ui.a2a.extension import try_activate_a2ui_extension

logger = logging.getLogger(__name__)

# --- Monkey-patch ADK to suppress mock_function_call_for_required_user_input ---
try:
  import google.adk.a2a.converters.to_adk_event as to_adk_event
  logger.info("--- Monkey-patching ADK _create_mock_function_call_for_required_user_input to be a no-op ---")
  to_adk_event._create_mock_function_call_for_required_user_input = lambda state, parts, ids: (parts, ids)
except Exception as e:
  logger.warning(f"--- Failed to monkey-patch ADK: {e} ---")


class QSRAgentExecutor(AgentExecutor):
  """QSR Insights-to-Action AgentExecutor."""

  def __init__(self, agent):
    self._agent = agent

  async def execute(
      self,
      context: RequestContext,
      event_queue: EventQueue,
  ) -> None:
    query = ""
    ui_event_part = None
    action = None

    logger.info(f"--- QSR_EXECUTOR: Full incoming message: {context.message.model_dump() if context.message else None} ---")
    logger.info(f"--- QSR_EXECUTOR: Requested extensions: {context.requested_extensions} ---")
    active_ui_version = try_activate_a2ui_extension(context, self._agent.agent_card)

    if active_ui_version:
      logger.info("--- QSR_EXECUTOR: A2UI extension is active. Using UI agent. ---")
    else:
      logger.info("--- QSR_EXECUTOR: A2UI extension is not active. Using text agent. ---")

    use_streaming = True
    form_user_input = None
    if context.message and context.message.parts:
      for i, part in enumerate(context.message.parts):
        if isinstance(part.root, DataPart):
          if "useStreaming" in part.root.data:
            use_streaming = part.root.data["useStreaming"]
          if part.root.data.get("version") == "v0.9" and "action" in part.root.data:
            ui_event_part = part.root.data["action"]
          elif "userAction" in part.root.data:
            ui_event_part = part.root.data["userAction"]
          if "user_input" in part.root.data:
            form_user_input = part.root.data["user_input"]

    if ui_event_part:
      logger.info(f"Received a2ui ClientEvent: {ui_event_part}")
      action = ui_event_part.get("name")
      ctx = ui_event_part.get("context", {})
      if isinstance(ctx, list):
        # Convert A2UI v0.8 context list of key-value maps to a standard dictionary
        ctx_dict = {}
        for entry in ctx:
          k = entry.get("key")
          v = entry.get("value")
          if k is not None:
            ctx_dict[k] = v
        ctx = ctx_dict

      if action == "get_action_items":
        store_id = ctx.get("store_id") or ctx.get("storeId") or "dublin_hq"
        date = ctx.get("date") or "2026-05-28"
        query = f"Show me the dashboard for {store_id} on {date}"
      elif action == "update_action_item_status":
        action_item_id = ctx.get("action_item_id") or ctx.get("actionItemId")
        status = ctx.get("status")
        # Direct instruction to perform the update and then display the active context
        query = f"Update compliance status of action item {action_item_id} to {status}."
      else:
        query = f"User submitted action: {action} with context: {ctx}"
    else:
      query = context.get_user_input()

    if not query and form_user_input:
      query = form_user_input
      logger.info(f"--- QSR_EXECUTOR: Recovered query from form parameter: '{query}' ---")

    logger.info(f"--- QSR_EXECUTOR: Final query for LLM: '{query}' ---")

    task = context.current_task
    if not task:
      task = new_task(context.message)
      await event_queue.enqueue_event(task)
    updater = TaskUpdater(event_queue, task.id, task.context_id)

    supported_catalogs = None
    if context.message and context.message.metadata:
      capabilities = context.message.metadata.get("a2uiClientCapabilities", {})
      if isinstance(capabilities, dict):
        supported_catalogs = capabilities.get("supportedCatalogIds", [])
        logger.info(f"--- QSR_EXECUTOR: client supportedCatalogIds: {supported_catalogs} ---")

    async for item in self._agent.stream(
        query,
        task.context_id,
        active_ui_version,
        use_streaming=use_streaming,
        supported_catalogs=supported_catalogs,
    ):
      is_task_complete = item["is_task_complete"]
      if not is_task_complete:
        message = None
        if "parts" in item:
          message = new_agent_parts_message(item["parts"], task.context_id, task.id)
        elif "updates" in item:
          message = new_agent_text_message(item["updates"], task.context_id, task.id)

        if message:
          await updater.update_status(TaskState.working, message)
        continue

      final_state = TaskState.completed

      message = None
      if "parts" in item:
        message = new_agent_parts_message(item["parts"], task.context_id, task.id)
      elif "updates" in item:
        message = new_agent_text_message(item["updates"], task.context_id, task.id)

      await updater.update_status(final_state, message)

  async def cancel(
      self, request: RequestContext, event_queue: EventQueue
  ) -> Task | None:
    raise ServerError(error=UnsupportedOperationError())
