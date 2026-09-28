from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import APIMasterError, base_url, download, get, poll, post

# Dify stops a plugin call after PLUGIN_MAX_EXECUTION_TIMEOUT (600 s by default), and video
# is slower than that: seedance-2.5 took about 15 minutes for 4 seconds. So this tool waits
# a little under the limit and, if the job is still rendering, hands back the task id for
# the Get Video tool instead of letting Dify kill the call and lose the job.
WAIT_SECONDS = 510


def _finished(tool: Tool, credentials, task_id: str, done: dict, model: str | None):
    # Some models (seedance) finish without a url field; the content endpoint always works.
    url = done.get("url") or f"{base_url(credentials)}/videos/{task_id}/content"
    yield tool.create_blob_message(blob=download(credentials, url), meta={"mime_type": "video/mp4"})
    yield tool.create_json_message({"model": model or done.get("model"), "task_id": task_id, "status": "completed", "url": url})


class VideoTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        credentials = self.runtime.credentials
        prompt = (tool_parameters.get("prompt") or "").strip()
        if not prompt:
            raise APIMasterError(None, "Prompt is required.")

        model = tool_parameters.get("model") or "seedance-2.5"
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "duration": int(tool_parameters.get("duration") or 4),
            "resolution": tool_parameters.get("resolution") or "720p",
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
        yield self.create_text_message(f"Submitted video task {task_id}. Video often takes 10-15 minutes…")

        done = poll(
            lambda: get(credentials, f"/videos/{task_id}"),
            lambda p: p.get("status") == "completed",
            lambda p: p.get("status") in ("failed", "error", "cancelled"),
            initial_delay=15.0,
            label="Video",
            max_seconds=WAIT_SECONDS,
            return_none_on_timeout=True,
        )
        if done is None:
            yield self.create_text_message(
                f"Still rendering after {WAIT_SECONDS // 60} minutes. The job is not lost: "
                f"run the Get Video tool with task id {task_id} in a few minutes."
            )
            yield self.create_json_message({"model": model, "task_id": task_id, "status": "in_progress"})
            return

        yield from _finished(self, credentials, task_id, done, model)
