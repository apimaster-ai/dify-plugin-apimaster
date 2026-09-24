from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools.client import IMAGE_TIMEOUT, APIMasterError, download, get, poll, post


class ImageTool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        credentials = self.runtime.credentials
        prompt = (tool_parameters.get("prompt") or "").strip()
        if not prompt:
            raise APIMasterError(None, "Prompt is required.")

        model = tool_parameters.get("model") or "gpt-image-2"
        resolution = tool_parameters.get("resolution") or "1k"
        use_async = bool(tool_parameters.get("async_mode"))

        body: dict[str, Any] = {"model": model, "prompt": prompt, "resolution": resolution}
        size = tool_parameters.get("size")
        if size and size != "auto":
            body["size"] = size
        references = (tool_parameters.get("reference_images") or "").strip()
        if references:
            body["image_urls"] = [u.strip() for u in references.split(",") if u.strip()]
        mask = (tool_parameters.get("mask_url") or "").strip()
        if mask:
            body["mask_url"] = mask

        if use_async:
            submit = post(credentials, "/images/generations/async", body, timeout=60)
            task_id = (submit.get("data") or [{}])[0].get("task_id")
            if not task_id:
                raise APIMasterError(None, f"No task_id in response: {str(submit)[:200]}")
            yield self.create_text_message(f"Submitted image task {task_id}, polling…")

            done = poll(
                lambda: get(credentials, f"/tasks/{task_id}", params={"model": model}),
                lambda p: (p.get("data") or p).get("status") == "completed",
                lambda p: (p.get("data") or p).get("status") in ("failed", "error", "cancelled"),
                initial_delay=12.0,
                label="Image",
            )
            payload = done.get("data") or done
            urls: list[str] = []
            for image in (payload.get("result") or {}).get("images", []):
                url = image.get("url")
                urls.extend(url if isinstance(url, list) else [url] if url else [])
        else:
            response = post(
                credentials,
                "/images/generations",
                body,
                timeout=IMAGE_TIMEOUT.get(resolution, 200),
            )
            urls = [item["url"] for item in response.get("data", []) if item.get("url")]

        if not urls:
            raise APIMasterError(None, "The endpoint returned no image URL.")

        for url in urls:
            # Both: the blob so the image is stored in Dify and survives the URL expiring,
            # and the link so a workflow can pass the URL downstream.
            yield self.create_blob_message(
                blob=download(credentials, url),
                meta={"mime_type": "image/png"},
            )
            yield self.create_link_message(url)
        yield self.create_json_message({"model": model, "prompt": prompt, "urls": urls})
