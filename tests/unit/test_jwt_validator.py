import time
import pytest
import jwt
from unittest.mock import MagicMock, patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from app.infrastructure.auth.jwt_validator import KeycloakJWTValidator


@pytest.fixture
def rsa_keypair():
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key = private_key.public_key()
    return pem_private, public_key


def test_jwt_validator_success(rsa_keypair):
    pem_private, public_key = rsa_keypair

    now = int(time.time())
    payload = {
        "sub": "user-walid-uuid",
        "email": "walid@example.com",
        "preferred_username": "walid",
        "realm_access": {"roles": ["USER", "ADMIN"]},
        "exp": now + 3600,
        "iat": now,
    }

    token = jwt.encode(payload, pem_private, algorithm="RS256", headers={"kid": "test-key-id"})

    validator = KeycloakJWTValidator(keycloak_url="http://localhost:8080", realm="doc-intelligence")

    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    with patch.object(validator.jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
        claims = validator.validate_token(token)
        assert claims["sub"] == "user-walid-uuid"
        assert claims["email"] == "walid@example.com"
        assert "ADMIN" in claims["realm_access"]["roles"]


def test_jwt_validator_expired_token(rsa_keypair):
    pem_private, public_key = rsa_keypair

    now = int(time.time())
    payload = {
        "sub": "user-expired",
        "exp": now - 300,  # Expired 5 mins ago
        "iat": now - 600,
    }

    token = jwt.encode(payload, pem_private, algorithm="RS256", headers={"kid": "test-key-id"})

    validator = KeycloakJWTValidator(keycloak_url="http://localhost:8080", realm="doc-intelligence")

    mock_signing_key = MagicMock()
    mock_signing_key.key = public_key

    with patch.object(validator.jwks_client, "get_signing_key_from_jwt", return_value=mock_signing_key):
        with pytest.raises(jwt.ExpiredSignatureError):
            validator.validate_token(token)
