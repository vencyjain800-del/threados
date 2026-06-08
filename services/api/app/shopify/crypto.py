import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.config import settings


def _kms_client():
    return boto3.client(
        "kms",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id or None,
        aws_secret_access_key=settings.aws_secret_access_key or None,
    )


def encrypt_token(plaintext: str) -> bytes:
    """Encrypt a Shopify access token via AWS KMS. Returns ciphertext bytes."""
    client = _kms_client()
    try:
        response = client.encrypt(
            KeyId=settings.kms_key_id,
            Plaintext=plaintext.encode(),
        )
        return response["CiphertextBlob"]
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError("KMS encryption failed") from exc


def decrypt_token(ciphertext: bytes) -> str:
    """Decrypt KMS-encrypted Shopify access token. Returns plaintext string."""
    client = _kms_client()
    try:
        response = client.decrypt(
            KeyId=settings.kms_key_id,
            CiphertextBlob=ciphertext,
        )
        return response["Plaintext"].decode()
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError("KMS decryption failed") from exc
