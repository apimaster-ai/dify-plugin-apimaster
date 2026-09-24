"""Validate every YAML against the Dify SDK's own pydantic models.

This is the same parsing Dify performs when it loads a plugin, so a green run here means
the manifest, the model provider, the predefined models and both tools are structurally
acceptable. No Dify instance, no key, no network.

    python -m pytest tests/ -q
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent


def load(rel: str) -> dict:
    return yaml.safe_load((ROOT / rel).read_text(encoding="utf-8"))


class TestManifest:
    def test_parses_against_the_sdk_model(self):
        from dify_plugin.core.entities.plugin.setup import PluginConfiguration

        config = PluginConfiguration(**load("manifest.yaml"))
        assert config.name == "apimaster"
        assert config.type.value == "plugin"

    def test_declares_both_extension_points(self):
        manifest = load("manifest.yaml")
        assert manifest["plugins"]["models"] == ["provider/apimaster.yaml"]
        assert manifest["plugins"]["tools"] == ["tools/apimaster.yaml"]

    def test_every_referenced_file_exists(self):
        manifest = load("manifest.yaml")
        for group in ("models", "tools"):
            for rel in manifest["plugins"].get(group, []):
                assert (ROOT / rel).is_file(), f"manifest points at a missing file: {rel}"
        assert (ROOT / "_assets" / manifest["icon"]).is_file()
        assert (ROOT / f"{manifest['meta']['runner']['entrypoint']}.py").is_file()

    def test_request_timeout_covers_a_4k_image(self):
        # A 4k render can legitimately take ten minutes; the default would abort it.
        source = (ROOT / "main.py").read_text(encoding="utf-8")
        assert "MAX_REQUEST_TIMEOUT" in source


class TestModelProvider:
    def test_parses_against_the_sdk_model(self):
        from dify_plugin.entities.model.provider import ProviderEntity

        raw = load("provider/apimaster.yaml")
        # `models` and `extra` are consumed by the loader, not by ProviderEntity itself.
        raw.pop("models", None)
        raw.pop("extra", None)
        provider = ProviderEntity(**raw)
        assert provider.provider == "apimaster"
        assert [m.value for m in provider.supported_model_types] == ["llm"]

    def test_offers_a_customizable_model_because_catalogs_change(self):
        provider = load("provider/apimaster.yaml")
        assert "customizable-model" in provider["configurate_methods"]
        assert "predefined-model" in provider["configurate_methods"]

    def test_base_url_default_keeps_the_v1_suffix(self):
        provider = load("provider/apimaster.yaml")
        fields = {f["variable"]: f for f in provider["provider_credential_schema"]["credential_form_schemas"]}
        assert fields["endpoint_url"]["default"].endswith("/v1")
        assert fields["api_key"]["type"] == "secret-input"

    def test_max_tokens_help_warns_about_reasoning_models(self):
        provider = load("provider/apimaster.yaml")
        fields = {f["variable"]: f for f in provider["model_credential_schema"]["credential_form_schemas"]}
        help_text = fields["max_tokens_to_sample"]["help"]["en_US"].lower()
        assert "reasoning" in help_text

    def test_python_sources_exist(self):
        extra = load("provider/apimaster.yaml")["extra"]["python"]
        assert (ROOT / extra["provider_source"]).is_file()
        for source in extra["model_sources"]:
            assert (ROOT / source).is_file()


class TestPredefinedModels:
    @pytest.mark.parametrize(
        "path", sorted(p.name for p in (ROOT / "models" / "llm").glob("*.yaml") if not p.name.startswith("_"))
    )
    def test_each_model_parses(self, path):
        from dify_plugin.entities.model.schema import AIModelEntity

        entity = AIModelEntity(**load(f"models/llm/{path}"))
        assert entity.model
        assert entity.model_type.value == "llm"

    def test_gpt5_does_not_expose_temperature(self):
        # Upstream metadata: temperature = false. Offering the slider invites a 400.
        rules = {r["name"] for r in load("models/llm/gpt-5.5.yaml")["parameter_rules"]}
        assert "temperature" not in rules and "top_p" not in rules

    def test_context_sizes_are_not_the_old_guesses(self):
        ctx = {p.stem: load(f"models/llm/{p.name}")["model_properties"]["context_size"]
               for p in (ROOT / "models" / "llm").glob("*.yaml") if not p.name.startswith("_")}
        assert ctx["gpt-5.5"] == 1_050_000
        assert ctx["claude-sonnet-4-6"] == 1_000_000

    def test_position_file_matches_the_shipped_models(self):
        position = load("models/llm/_position.yaml")
        shipped = {p.stem for p in (ROOT / "models" / "llm").glob("*.yaml") if not p.name.startswith("_")}
        assert set(position) == shipped, "_position.yaml and the model files disagree"

    def test_model_ids_are_ones_the_gateway_actually_serves(self):
        # Verified against GET /v1/models on 2026-09-22. Wrong ids are the single most
        # common cause of a "plugin is broken" report.
        verified = {"gpt-5.5", "claude-sonnet-4-6", "deepseek-v4-pro", "glm-5.3-flash"}
        shipped = {p.stem for p in (ROOT / "models" / "llm").glob("*.yaml") if not p.name.startswith("_")}
        assert shipped <= verified, f"unverified model ids: {shipped - verified}"


class TestTools:
    def test_provider_parses_against_the_sdk_model(self):
        from dify_plugin.entities.tool import ToolProviderConfiguration

        raw = load("tools/apimaster.yaml")
        provider = ToolProviderConfiguration(**raw)
        assert provider.identity.name == "apimaster"

    @pytest.mark.parametrize("name", ["image", "video"])
    def test_each_tool_parses(self, name):
        from dify_plugin.entities.tool import ToolConfiguration

        tool = ToolConfiguration(**load(f"tools/{name}.yaml"))
        assert tool.identity.name == name
        assert tool.description.llm, "an empty llm description makes the tool unusable by an agent"

    @pytest.mark.parametrize("name", ["image", "video"])
    def test_prompt_is_required_and_llm_fillable(self, name):
        params = {p["name"]: p for p in load(f"tools/{name}.yaml")["parameters"]}
        assert params["prompt"]["required"] is True
        assert params["prompt"]["form"] == "llm"

    def test_tool_sources_exist(self):
        provider = load("tools/apimaster.yaml")
        assert (ROOT / provider["extra"]["python"]["source"]).is_file()
        for rel in provider["tools"]:
            tool = load(rel)
            assert (ROOT / tool["extra"]["python"]["source"]).is_file()

    def test_media_model_ids_are_verified(self):
        verified_image = {
            "gpt-image-2",
            "doubao-seedream-5-0-pro-260628",
            "gemini-3.1-flash-image",
            "midjourney-v8.2",
            "midjourney-niji-7",
        }
        verified_video = {
            "sora-2",
            "sora-2-pro",
            "seedance-2.5",
            "seedance-2.0",
            "kling-v3-motion-control",
            "kling-v3-omni",
            "MiniMax-H3",
            "grok-imagine-video-1.5",
        }
        for name, verified in (("image", verified_image), ("video", verified_video)):
            params = {p["name"]: p for p in load(f"tools/{name}.yaml")["parameters"]}
            offered = {o["value"] for o in params["model"]["options"]}
            assert offered <= verified, f"{name}: unverified ids {offered - verified}"

    def test_video_warns_about_the_portrait_trap(self):
        params = {p["name"]: p for p in load("tools/video.yaml")["parameters"]}
        assert "16:9" in params["aspect_ratio"]["human_description"]["en_US"]


class TestPythonSources:
    def test_all_modules_compile(self):
        import py_compile

        for path in ROOT.rglob("*.py"):
            if "__pycache__" in str(path) or path.parts[-2] == "tests":
                continue
            py_compile.compile(str(path), doraise=True)

    def test_download_compares_hosts_not_prefixes(self):
        # Generated media lives on the same domain but outside /v1; prefix matching
        # silently drops the bearer token.
        source = (ROOT / "tools" / "client.py").read_text(encoding="utf-8")
        assert "urlparse" in source and "netloc" in source
