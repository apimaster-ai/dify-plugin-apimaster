import logging

from dify_plugin import OAICompatProvider
from dify_plugin.errors.model import CredentialsValidateFailedError

logger = logging.getLogger(__name__)


class APIMasterProvider(OAICompatProvider):
    """The base class treats provider credentials as always valid.

    That makes the "Save" button in Dify meaningless: a wrong key or a base URL missing
    its /v1 suffix is only discovered later, inside a workflow run. Validating here turns
    those into an immediate, readable error.
    """

    def validate_provider_credentials(self, credentials: dict) -> None:
        import requests

        endpoint = str(credentials.get("endpoint_url") or "").rstrip("/")
        api_key = str(credentials.get("api_key") or "").strip()

        if not api_key:
            raise CredentialsValidateFailedError("API key is empty.")
        if not endpoint:
            raise CredentialsValidateFailedError("Base URL is empty.")
        if not endpoint.endswith("/v1"):
            raise CredentialsValidateFailedError(
                f"Base URL should end with /v1 (got {endpoint}). "
                "The Anthropic-compatible root URL does not work here."
            )

        try:
            response = requests.get(
                f"{endpoint}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
        except requests.RequestException as exc:
            raise CredentialsValidateFailedError(f"Cannot reach {endpoint}: {exc}") from exc

        if response.status_code == 401:
            raise CredentialsValidateFailedError(
                "Unauthorized. The key is wrong, expired, or was copied with whitespace."
            )
        if response.status_code == 402:
            raise CredentialsValidateFailedError("Insufficient balance on this account.")
        if response.status_code == 404:
            raise CredentialsValidateFailedError(
                f"{endpoint}/models returned 404. Check the Base URL."
            )
        if response.status_code != 200:
            raise CredentialsValidateFailedError(
                f"HTTP {response.status_code} from {endpoint}/models: {response.text[:160]}"
            )

        try:
            count = len(response.json().get("data", []))
        except ValueError as exc:
            raise CredentialsValidateFailedError(
                "The endpoint did not return JSON. Is the Base URL an OpenAI-compatible API?"
            ) from exc

        logger.info("APIMaster credentials validated, %s models available", count)
