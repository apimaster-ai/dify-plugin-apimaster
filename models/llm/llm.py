# Import the module, not the class: Dify rejects the file if more than one
# LargeLanguageModel subclass (the imported base included) is visible at module level.
import dify_plugin


class APIMasterLargeLanguageModel(dify_plugin.OAICompatLargeLanguageModel):
    """Thin subclass of Dify's OpenAI-compatible LLM.

    Everything this gateway needs — streaming, tool calls, vision, usage — is already
    implemented there. Re-implementing it would mean re-fixing the same bugs, so the only
    thing added here is a default endpoint so a customizable model still works when the
    user leaves the Base URL empty.
    """

    DEFAULT_ENDPOINT = "https://apimaster.ai/v1"

    def _add_defaults(self, credentials: dict) -> dict:
        if not credentials.get("endpoint_url"):
            credentials["endpoint_url"] = self.DEFAULT_ENDPOINT
        return credentials

    def _invoke(self, model, credentials, prompt_messages, model_parameters, tools=None, stop=None, stream=True, user=None):
        return super()._invoke(
            model,
            self._add_defaults(credentials),
            prompt_messages,
            model_parameters,
            tools,
            stop,
            stream,
            user,
        )

    def validate_credentials(self, model: str, credentials: dict) -> None:
        super().validate_credentials(model, self._add_defaults(credentials))
