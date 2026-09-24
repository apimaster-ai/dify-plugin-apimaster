from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import APIMasterError, base_url, download, get, poll, post


class VideoTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        credentials = self.runtime.credentials
        prompt = (tool_parameters.get("prompt") or "").strip()
        if not prompt:
            raise APIMasterError(None, "Prompt is required.")

        model = tool_parameters.get("model") or "sora-2"
        resolution = tool_parameters.get("resolution") or "720p"
        if model == "sora-2" and resolution != "720p":
            # sora-2 serves 720p only; silently sending 1080p wastes a job.
            resolution = "720p"

        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "duration": int(tool_parameters.get("duration") or 4),
            "resolution": resolution,
            # Explicit on purpose: a portrait reference with no aspect comes back 16:9.
            "aspect_ratio": tool_parameters.get("aspect_ratio") or "16:9",
        }
        reference = (tool_parameters.get("reference_image") or "").strip()
        if reference:
            body["image_urls"] = [reference]

        submit = post(credentials, "/videos/generations", body, timeout=60)
        task_id = (submit.get("data") or [{}])[0].get("task_id") or submit.get("id")
        if not task_id:
            raise APIMasterError(None, f"No task id in response: {str(submit)[:200]}")
        yield self.create_text_message(f"Submitted video task {task_id}, usually 1-3 minutes…")

        done = poll(
            lambda: get(credentials, f"/videos/{task_id}"),
            lambda p: p.get("status") == "completed",
            lambda p: p.get("status") in ("failed", "error", "cancelled"),
            initial_delay=15.0,
            label="Video",
        )

        url = done.get("url") or f"{base_url(credentials)}/videos/{task_id}/content"
        yield self.create_blob_message(
            blob=download(credentials, url),
            meta={"mime_type": "video/mp4"},
        )
        yield self.create_json_message({"model": model, "task_id": task_id, "url": url})
