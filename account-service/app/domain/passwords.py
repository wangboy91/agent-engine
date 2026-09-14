"""Password hashing — domain policy, no I/O."""

from __future__ import annotations

import hashlib
import hmac
import secrets

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("password must be at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _ITERATIONS, dklen=32
    )
    return f"{_ALGO}${_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, iter_s, salt_hex, hash_hex = encoded.split("$", 3)
        if algo != _ALGO:
            return False
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=32
    )
    return hmac.compare_digest(digest, expected)


def needs_rehash(encoded: str) -> bool:
    try:
        algo, iter_s, _s, _h = encoded.split("$", 3)
        return algo != _ALGO or int(iter_s) < _ITERATIONS
    except (ValueError, TypeError):
        return True
