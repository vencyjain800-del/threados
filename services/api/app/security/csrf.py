import hashlib
import hmac
import secrets

from fastapi import HTTPException, Request, status

from app.config import settings

CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "threados_csrf"
_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _sign(token: str) -> str:
    return hmac.new(
        settings.csrf_secret.encode(),
        token.encode(),
        hashlib.sha256,
    ).hexdigest()


def validate_csrf(request: Request) -> None:
    if request.method in _SAFE_METHODS:
        return

    origin = request.headers.get("origin")
    if origin and origin not in (settings.app_url, settings.api_url):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid origin")

    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)

    if not cookie_token or not header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token missing")

    if not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")
