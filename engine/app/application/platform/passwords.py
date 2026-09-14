"""Password hashing utilities (stdlib PBKDF2-HMAC-SHA256). Never store plaintext."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets

_ITERATIONS = 390_000
_ALGO = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    """Return ``pbkdf2_sha256$iterations$salt_hex$hash_hex``."""
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
        algo, iter_s, _salt, _hash = encoded.split("$", 3)
        return algo != _ALGO or int(iter_s) < _ITERATIONS
    except (ValueError, TypeError):
        return True


def random_temp_password(length: int = 12) -> str:
    alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def env_seed_password() -> str:
    """Optional override for first-time seed from environment."""
    return os.getenv("AGENT_ENGINE_SEED_ADMIN_PASSWORD", "")
