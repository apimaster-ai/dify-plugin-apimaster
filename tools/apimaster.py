from typing import Any

from dify_plugin import ToolProvider
from dify_plugin.errors.tool import ToolProviderCredentialValidationError

from tools.client import APIMasterError, base_url, get


class APIMasterMediaProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        endpoint = base_url(credentials)
        if not endpoint.endswith("/v1"):
            raise ToolProviderCredentialValidationError(
                f"Base URL should end with /v1 (got {endpoint})."
            )
        try:
            # Cheapest call that proves both the key and the URL are right.
            get(credentials, "/models", timeout=30)
        except APIMasterError as exc:
            raise ToolProviderCredentialValidationError(str(exc)) from exc
        except Exception as exc:  # network failures surface as a readable message too
            raise ToolProviderCredentialValidationError(f"Cannot reach {endpoint}: {exc}") from exc
