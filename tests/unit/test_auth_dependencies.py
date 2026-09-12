import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.dependencies import get_current_user_id


def test_get_current_user_id_missing_credentials_raises_401(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    mock_session = MagicMock()

    with pytest.raises(HTTPException) as exc_info:
        get_current_user_id(credentials=None, session=mock_session)

    assert exc_info.value.status_code == 401
    assert "Bearer token missing" in exc_info.value.detail


def test_get_current_user_id_invalid_token_raises_401(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    mock_session = MagicMock()
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="invalid-jwt-token")

    with patch("app.api.dependencies.jwt_validator.validate_token") as mock_validate:
        mock_validate.side_effect = Exception("Signature verification failed")

        with pytest.raises(HTTPException) as exc_info:
            get_current_user_id(credentials=creds, session=mock_session)

        assert exc_info.value.status_code == 401
        assert "Invalid or expired" in exc_info.value.detail


def test_get_current_user_id_valid_token_extracts_sub(monkeypatch):
    monkeypatch.setenv("AUTH_ENABLED", "true")
    mock_session = MagicMock()
    mock_session.query.return_value.filter_by.return_value.first.return_value = MagicMock()

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="valid-jwt-token")

    with patch("app.api.dependencies.jwt_validator.validate_token") as mock_validate:
        mock_validate.return_value = {
            "sub": "user-uuid-1234",
            "preferred_username": "walid",
            "email": "walid@example.com",
            "realm_access": {"roles": ["USER", "ADMIN"]},
        }

        user_id = get_current_user_id(credentials=creds, session=mock_session)

        assert user_id == "user-uuid-1234"


def test_get_current_user_id_reconciles_subject_change(monkeypatch):
    """When a user's Keycloak UUID changes, auto-reconcile user.id and documents."""
    monkeypatch.setenv("AUTH_ENABLED", "true")
    mock_session = MagicMock()

    # Existing user in DB with old UUID
    existing_user = MagicMock()
    existing_user.id = "old-keycloak-uuid"
    existing_user.email = "walid@example.com"
    existing_user.role = "USER"
    mock_session.query.return_value.filter_by.return_value.first.return_value = existing_user

    new_sub = "new-keycloak-uuid-5678"
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="new-jwt-token")

    with patch("app.api.dependencies.jwt_validator.validate_token") as mock_validate:
        mock_validate.return_value = {
            "sub": new_sub,
            "email": "walid@example.com",
            "realm_access": {"roles": ["USER", "ADMIN"]},
        }

        user_id = get_current_user_id(credentials=creds, session=mock_session)

        assert user_id == new_sub
        assert existing_user.id == new_sub
        assert existing_user.role == "ADMIN"
        mock_session.commit.assert_called()
