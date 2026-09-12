import os
import logging
from typing import Dict, Any, Optional
import jwt
from jwt import PyJWKClient, PyJWTError

logger = logging.getLogger(__name__)


class KeycloakJWTValidator:
    """Validates Keycloak JWT Bearer tokens against the realm JWKS endpoint."""

    def __init__(
        self,
        keycloak_url: Optional[str] = None,
        realm: Optional[str] = None,
        client_id: Optional[str] = None,
    ) -> None:
        self.keycloak_url = (
            keycloak_url
            or os.getenv("KEYCLOAK_INTERNAL_URL")
            or os.getenv("KEYCLOAK_URL")
            or "http://localhost:8080"
        ).rstrip("/")
        self.realm = realm or os.getenv("KEYCLOAK_REALM", "doc-intelligence")
        self.client_id = client_id or os.getenv("KEYCLOAK_CLIENT_ID", "doc-intelligence-ui")
        self.jwks_url = f"{self.keycloak_url}/realms/{self.realm}/protocol/openid-connect/certs"
        self._jwks_client: Optional[PyJWKClient] = None

    @property
    def jwks_client(self) -> PyJWKClient:
        if self._jwks_client is None:
            self._jwks_client = PyJWKClient(self.jwks_url, cache_jwk_set=True, lifespan=3600)
        return self._jwks_client

    def validate_token(self, token: str) -> Dict[str, Any]:
        """Validate and decode a Keycloak Bearer JWT.

        Args:
            token: Raw Bearer JWT string.

        Returns:
            Dict containing the verified claims (sub, email, preferred_username, roles, etc.).

        Raises:
            PyJWTError: If the token is invalid, expired, or untrusted.
        """
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(token)

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_aud": False,  # Client-side SPA tokens may have azp or realm audience
                },
            )
            return payload
        except Exception as exc:
            logger.warning("Keycloak token validation failed: %s", exc)
            raise exc
