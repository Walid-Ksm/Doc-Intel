import os
import logging
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.infrastructure.database.session import SessionLocal
from app.infrastructure.database.models import UserModel
from app.infrastructure.auth.jwt_validator import KeycloakJWTValidator

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
jwt_validator = KeycloakJWTValidator()


def get_db_session():
    """Yield a database session and ensure it is closed after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_current_user_id(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    session: Session = Depends(get_db_session),
) -> str:
    """Returns the authenticated user's ID from Keycloak JWT or fallback.

    Auto-provisions the user in the PostgreSQL users table upon first valid login.
    """
    auth_enabled = os.getenv("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")

    if not auth_enabled:
        return "user-123"

    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Bearer token missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials

    try:
        payload = jwt_validator.validate_token(token)
    except Exception as exc:
        logger.warning("Token validation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired authentication token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject (sub) claim.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reconcile or auto-provision user in PostgreSQL
    email = payload.get("email") or f"{payload.get('preferred_username', user_id)}@example.com"
    realm_access = payload.get("realm_access", {})
    roles = realm_access.get("roles", [])
    role = "ADMIN" if "ADMIN" in roles else "USER"

    # 1. Primary lookup by email (stable business identity anchor)
    user_by_email = session.query(UserModel).filter_by(email=email).first()

    if user_by_email is not None:
        if getattr(user_by_email, "id", None) != user_id:
            # Keycloak IdP subject changed (realm reset, re-import, or environment migration).
            # Reconcile all existing documents to the new active Keycloak UUID automatically.
            logger.info(
                "Identity reconciliation for '%s': migrating user ID %s -> %s",
                email,
                user_by_email.id,
                user_id,
            )
            try:
                from app.infrastructure.database.models import DocumentModel

                session.query(DocumentModel).filter(
                    DocumentModel.user_id == user_by_email.id
                ).update({DocumentModel.user_id: user_id}, synchronize_session=False)

                user_by_email.id = user_id
                user_by_email.role = role
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.warning("Failed identity reconciliation migration: %s", exc)
        else:
            if getattr(user_by_email, "role", None) != role:
                try:
                    user_by_email.role = role
                    session.commit()
                except Exception:
                    session.rollback()
    else:
        # 2. Check if user already exists by ID (e.g. user updated their email address)
        user_by_id = session.query(UserModel).filter_by(id=user_id).first()
        if user_by_id is not None:
            try:
                user_by_id.email = email
                user_by_id.role = role
                session.commit()
            except Exception:
                session.rollback()
        else:
            # 3. Fresh user auto-provisioning
            try:
                new_user = UserModel(id=user_id, email=email, role=role)
                session.add(new_user)
                session.commit()
            except Exception as exc:
                session.rollback()
                logger.debug("User auto-provisioning handled race condition: %s", exc)

    return user_id
