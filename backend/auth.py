"""Email + password auth — stdlib only (no bcrypt/jwt dependency).

PBKDF2-HMAC-SHA256 for password hashing, opaque random session tokens.
ponytail: one session token per founder, no expiry/rotation-on-idle. Add a
sessions table + TTL if you need multi-device or server-side revocation lists.
"""
import hashlib
import hmac
import secrets

_ITERATIONS = 240_000
_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_PREFIX}${_ITERATIONS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        prefix, iters, salt_hex, hash_hex = stored.split("$")
        if prefix != _PREFIX:
            return False
        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iters)
        )
        return hmac.compare_digest(dk.hex(), hash_hex)  # constant-time
    except Exception:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


if __name__ == "__main__":
    # ponytail self-check: round-trip + reject wrong password + reject tampered hash
    h = hash_password("correct horse battery")
    assert verify_password("correct horse battery", h)
    assert not verify_password("wrong", h)
    assert not verify_password("correct horse battery", "garbage")
    assert new_token() != new_token()
    print("auth self-check ok")
