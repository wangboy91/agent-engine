"""HMAC signed principal tokens (shared secret with engine for 1.0.1)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from typing import Any

from app.infrastructure.config import token_secret


class HmacTokenSigner:
    def issue(self, principal: dict[str, object]) -> str:
        raw = json.dumps(principal, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        payload = _b64url(raw)
        return f"dev.{payload}.{_sign(payload.encode('ascii'), token_secret())}"

    def parse(self, token: str) -> dict[str, Any] | None:
        if not token.startswith("dev."):
            return None
        parts = token.split(".")
        if len(parts) != 3:
            return None
        _, payload, sig = parts
        if not hmac.compare_digest(
            _sign(payload.encode("ascii"), token_secret()), sig
        ):
            return None
        try:
            data = json.loads(_b64url_decode(payload).decode("utf-8"))
            return data if isinstance(data, dict) else None
        except Exception:  # noqa: BLE001
            return None


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _sign(payload: bytes, secret: bytes) -> str:
    return _b64url(hmac.new(secret, payload, hashlib.sha256).digest())
