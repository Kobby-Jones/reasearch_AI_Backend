"""Domain-level exceptions mapped to HTTP responses in the API layer."""
from __future__ import annotations


class RAIError(Exception):
    """Base error."""

    status_code: int = 400

    def __init__(self, detail: str):
        self.detail = detail
        super().__init__(detail)


class NotFoundError(RAIError):
    status_code = 404


class AuthError(RAIError):
    status_code = 401


class PermissionError(RAIError):
    status_code = 403


class FeatureLockedError(PermissionError):
    """Raised by the service layer when a plan does not allow a feature."""


class UsageLimitError(RAIError):
    status_code = 429


class PaymentError(RAIError):
    status_code = 402


class ValidationError(RAIError):
    status_code = 422


class AIGenerationError(RAIError):
    """Raised when the AI returns an empty or unparseable result after retries."""

    status_code = 502
