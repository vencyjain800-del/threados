import base64
import hashlib
import hmac

from fastapi import HTTPException, Request, status

from app.config import settings


async def verify_webhook_hmac(request: Request) -> bytes:
    """
    Verify X-Shopify-Hmac-Sha256 against the raw request body.
    Returns the raw body for downstream use. Raises 401 on failure.
    """
    body = await request.body()
    received = request.headers.get("X-Shopify-Hmac-Sha256", "")

    digest = base64.b64encode(
        hmac.new(
            settings.shopify_api_secret.encode(),
            body,
            hashlib.sha256,
        ).digest()
    ).decode()

    if not hmac.compare_digest(digest, received):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")

    return body
