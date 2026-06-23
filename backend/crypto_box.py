"""Encryption-at-rest for stored integration secrets (IntegrationState.access_token).

Symmetric Fernet (AES-128-CBC + HMAC-SHA256). The key comes from DCERN_SECRET_KEY
(a Fernet key). If unset, encryption is a NO-OP (values stored plaintext) so dev/test
boots without a key — SET IT IN PROD. Encrypted values carry an 'enc:' prefix so we
can still read legacy plaintext rows written before the key existed (graceful migration).

Generate a key:
    python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
import logging
import os

logger = logging.getLogger(__name__)
_PREFIX = "enc:"


def _box():
    key = os.getenv("DCERN_SECRET_KEY")
    if not key:
        return None
    from cryptography.fernet import Fernet
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_secret(plaintext):
    """Encrypt for storage. Returns plaintext unchanged if no key is configured."""
    if plaintext is None:
        return plaintext
    box = _box()
    if not box:
        logger.warning("DCERN_SECRET_KEY unset — storing integration secret in PLAINTEXT")
        return plaintext
    return _PREFIX + box.encrypt(plaintext.encode()).decode()


def decrypt_secret(stored):
    """Inverse of encrypt_secret. Legacy (unprefixed) plaintext is returned as-is."""
    if not stored or not stored.startswith(_PREFIX):
        return stored
    box = _box()
    if not box:
        logger.error("encrypted secret present but DCERN_SECRET_KEY unset — cannot decrypt")
        return ""
    try:
        return box.decrypt(stored[len(_PREFIX):].encode()).decode()
    except Exception as e:
        logger.error(f"failed to decrypt integration secret: {e}")
        return ""


if __name__ == "__main__":
    from cryptography.fernet import Fernet
    os.environ["DCERN_SECRET_KEY"] = Fernet.generate_key().decode()
    enc = encrypt_secret("sk_live_supersecret")
    assert enc.startswith(_PREFIX) and "supersecret" not in enc, enc
    assert decrypt_secret(enc) == "sk_live_supersecret"
    assert decrypt_secret("legacy-plaintext") == "legacy-plaintext"  # backward-compatible read
    assert decrypt_secret(None) is None and encrypt_secret(None) is None
    del os.environ["DCERN_SECRET_KEY"]
    assert encrypt_secret("x") == "x"  # no key -> no-op passthrough
    print("crypto_box self-check ok")
