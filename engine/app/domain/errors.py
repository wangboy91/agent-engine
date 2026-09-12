"""Structured error primitives."""

from typing import Any


class BklEngineError(Exception):
    """Base exception for expected engine errors."""

    def __init__(
        self,
        code: str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
        retryable: bool = False,
    ) -> None:
        self.code = code
        self.message = message or code
        self.details = details or {}
        self.retryable = retryable
        super().__init__(f"{self.code}: {self.message}")
