"""Authentication and authorization module.

When ``settings.auth_enabled`` is True, middleware enforces JWT bearer tokens
on all routes except the health probes and the login endpoint.

Tokens are obtained via ``POST /auth/token`` with username / password
credentials validated against the ``auth_admin_*`` settings.  In production,
replace the credential check with a real user store.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.core.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)

# -- Public paths that bypass auth even when enabled --
PUBLIC_PATHS: set[str] = {
    "/health",
    "/health/live",
    "/health/ready",
    "/info",
    "/auth/token",
    "/docs",
    "/docs/oauth2-redirect",
    "/openapi.json",
    "/redoc",
}


# -- Schemas --

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# -- Token helpers --

def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.auth_access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.auth_secret_key, algorithm=settings.auth_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.auth_secret_key, algorithms=[settings.auth_algorithm])


# -- Dependency --

async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
) -> dict[str, Any] | None:
    """Return token payload if auth is enabled, else None (open access)."""
    if not settings.auth_enabled:
        return None

    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# -- Routes --

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtain access token",
    description="Authenticate with username and password to receive a JWT access token.",
)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenResponse:
    # In production, replace this with a real user lookup + password hash check
    if (
        form_data.username != settings.auth_admin_username
        or form_data.password != settings.auth_admin_password
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expires = timedelta(minutes=settings.auth_access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": form_data.username, "role": "admin"},
        expires_delta=expires,
    )
    return TokenResponse(
        access_token=access_token,
        expires_in=int(expires.total_seconds()),
    )
