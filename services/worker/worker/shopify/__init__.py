"""
Shopify API client package.

Usage in a job:
    from worker.shopify import ShopifyClient, decrypt_token

    token = decrypt_token(connection.access_token_enc)
    with ShopifyClient(shop=connection.shop_domain, access_token=token) as client:
        for page in client.iter_products():
            ...
"""
from worker.shopify.client import ShopifyClient, ShopifyRateLimitError
from worker.shopify.crypto import decrypt_token

__all__ = ["ShopifyClient", "ShopifyRateLimitError", "decrypt_token"]
