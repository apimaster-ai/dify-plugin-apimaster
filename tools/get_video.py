from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import APIMasterError, get
from tools.video import _finished


class GetVideoTool(Tool):
    """Check a video job submitted earlier, and return the MP4 once it is finished."""

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        credentials = self.runtime.credentials
        task_id = (tool_parameters.get("task_id") or "").strip()
        if not task_id:
            raise APIMasterError(None, "Task id is required.")

        status = get(credentials, f"/videos/{task_id}")
        state = status.get("status")
        if state == "completed":
            yield from _finished(self, credentials, task_id, status, None)
            return
        if state in ("failed", "error", "cancelled"):
            raise APIMasterError(None, f"Video job {state}: {str(status)[:200]}")

        progress = status.get("progress")
        yield self.create_text_message(
            f"Video task {task_id} is {state or 'queued'}"
            + (f" ({progress}%)" if progress is not None else "")
            + ". Try again in a few minutes."
        )
        yield self.create_json_message({"task_id": task_id, "status": state, "progress": progress})
