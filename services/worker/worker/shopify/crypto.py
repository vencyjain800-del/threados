"""
KMS token decryption for the worker service.

The Shopify access token is stored KMS-encrypted (BYTEA) in
shopify_connections.access_token_enc.  Decrypt it here before passing the
plaintext to ShopifyClient.

This module is intentionally self-contained — the worker shares no code with
the API service (services/api/app/shopify/crypto.py).  Both call boto3 directly.

Environment variables
---------------------
AWS_REGION              Default "eu-west-2"
AWS_ACCESS_KEY_ID       Falls back to IAM role credentials if unset
AWS_SECRET_ACCESS_KEY   Falls back to IAM role credentials if unset
KMS_KEY_ID              ARN or alias of the KMS key used to encrypt
"""
from __future__ import annotations

import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError


def decrypt_token(ciphertext: bytes) -> str:
    """Decrypt a KMS-encrypted Shopify access token.

    Parameters
    ----------
    ciphertext:
        Raw bytes as stored in ``shopify_connections.access_token_enc``.

    Returns
    -------
    str
        The plaintext access token, ready to pass to :class:`~worker.shopify.client.ShopifyClient`.

    Raises
    ------
    RuntimeError
        Wraps any ``BotoCoreError`` or ``ClientError`` from the KMS call.
    """
    client = boto3.client(
        "kms",
        region_name=os.environ.get("AWS_REGION", "eu-west-2"),
        # Explicit keys are optional — boto3 falls back to IAM role / env vars automatically
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID") or None,
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
    )
    try:
        response = client.decrypt(
            KeyId=os.environ.get("KMS_KEY_ID", ""),
            CiphertextBlob=ciphertext,
        )
        return response["Plaintext"].decode()
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError("KMS decryption of Shopify access token failed") from exc
