from collections.abc import Generator
import hmac

from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def require_auth(request: Request) -> None:
    """Fail-closed bearer-token authentication for the single-owner API.

    Every protected route requires "Authorization: Bearer <token>" matching
    the API_AUTH_TOKEN setting. Comparison is constant-time. When the token
    is not configured, every protected route returns 503 rather than
    degrading to open access. Never logs or echoes the token.
    """
    expected = get_settings().api_auth_token

    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Authentication is not configured on this server. "
                "Set API_AUTH_TOKEN and restart the API."
            ),
        )

    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed credentials. Expected 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )