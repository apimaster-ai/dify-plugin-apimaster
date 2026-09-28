# APIMaster for Dify

A Dify plugin that adds two things the built-in OpenAI-compatible provider cannot do on
its own:

1. **Chat models** from [APIMaster](https://apimaster.ai/docs) — preconfigured, with a
   credential check that actually verifies your key when you press Save.
2. **Image and video generation tools** — `gpt-image-2`, Seedream, Midjourney, Seedance,
   Kling, MiniMax H3 — usable inside any workflow or agent.

Works against any other OpenAI-compatible gateway too: change the Base URL.

Source code: https://github.com/apimaster-ai/dify-plugin-apimaster

## Requirements

- An APIMaster API key ([get one here](https://apimaster.ai/docs/getting-started/api-key)),
  or a key for whichever OpenAI-compatible gateway you point the Base URL at.
- Outbound HTTPS from your Dify instance to `apimaster.ai`, or to the host in your Base URL.
  Generated images and videos are downloaded from the URLs the gateway returns.

## Install

From the Dify marketplace, search for **APIMaster**.

To install from source:

```bash
dify plugin package ./dify-plugin-apimaster
# then upload the resulting .difypkg in Dify → Plugins → Install from local
```

## Configure

**Settings → Model Provider → APIMaster**

| Field | Value |
| --- | --- |
| API Key | from the [console](https://apimaster.ai/docs/getting-started/api-key) |
| Base URL | `https://apimaster.ai/v1` |

Press Save. Unlike the generic OpenAI-compatible provider, this one calls `/models`
before accepting the credential, so a wrong key or a Base URL missing its `/v1` fails
immediately with a readable message instead of surfacing later inside a workflow run.

For the media tools, configure the same credential under **Tools → APIMaster Media**.

## Models

Four models ship predefined: `gpt-5.5`, `claude-sonnet-4-6`, `deepseek-v4-pro`,
`glm-5.3-flash`. Every id was verified against `GET /v1/models`, and context sizes and
capabilities come from the models.dev canonical entries. `gpt-5.5` deliberately has no
temperature slider: the model does not accept one.

The catalog changes, so the provider also supports **customizable models**: add any id
the endpoint serves through *Add Model*. List what is available with:

```bash
curl -s https://apimaster.ai/v1/models \
  -H "Authorization: Bearer $APIMASTER_API_KEY" | jq -r '.data[].id'
```

### One setting worth getting right

**Max output tokens.** Most models on this gateway are reasoning models: they spend part
of the token budget on hidden reasoning before emitting any visible text. Measured on one
model, a 64-token budget was consumed 59 tokens by reasoning and the answer came back
empty; at 256 it answered correctly. If a model returns nothing, raise this before
assuming it is broken.

## Tools

### Generate Image

Text-to-image, image-to-image (comma-separated reference URLs) and inpainting (mask URL).
Aspect ratio and 1K/2K/4K resolution.

**Turn on "Submit and poll" for 2K and 4K.** A single synchronous request at those sizes
can exceed the gateway's own timeout and return a 408; async mode submits the job and
polls instead.

The tool emits the image three ways: as a file (so it survives the URL expiring), as a
link, and as JSON with all the URLs — use whichever your workflow needs.

### Generate Video

Text-to-video and image-to-video. 4–20 seconds, 720p (higher tiers depend on the model),
landscape or portrait. Submits, polls, and returns the MP4 as a file.

**Video is slow, and Dify has a time limit.** `seedance-2.5` took about 15 minutes for a
4-second clip, while Dify stops a plugin call after 10 minutes by default
(`PLUGIN_MAX_EXECUTION_TIMEOUT=600`). So the tool waits about 8.5 minutes; if the job is
still rendering it returns `{"task_id": ..., "status": "in_progress"}` instead of failing.

### Get Video

Takes that `task_id` and returns the MP4 once the job has finished, or its status and
progress if not. In a workflow, put it after Generate Video behind a wait or a loop; an
agent can simply call it again later. Nothing is lost if you check back late.

**Always set Aspect ratio when you pass a reference image.** A portrait reference with no
aspect ratio is treated as 16:9 by the gateway and comes back letterboxed.


## Use it with another gateway

Nothing here is vendor-locked. Point the Base URL at any endpoint that implements
`/v1/chat/completions`, `/v1/images/generations` and `/v1/videos/generations`. The model
dropdowns are suggestions; the customizable-model path takes any id.

## Development

```bash
pip install -r requirements.txt pytest pyyaml
python -m pytest tests/ -q
```

The tests parse `manifest.yaml`, the provider, every predefined model and both tools
against the **Dify SDK's own pydantic models** — the same validation Dify performs when
it loads a plugin. They also assert that every shipped model id is one the gateway really
serves, because a stale id is the most common cause of a "plugin is broken" report.

No Dify instance, no API key and no network access are required to run them.

## Privacy

See [PRIVACY.md](PRIVACY.md). The plugin stores nothing and sends data only to the
endpoint you configure.

## License

MIT
