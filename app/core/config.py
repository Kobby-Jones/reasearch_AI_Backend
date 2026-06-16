"""Centralised application settings (Pydantic v2 / pydantic-settings)."""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # App
    app_name: str = "ResearchAI Backend (RAI-Core)"
    environment: str = "development"
    debug: bool = True
    api_prefix: str = "/api/v1"
    # Comma-separated list of allowed browser origins, or "*" for any (dev only).
    cors_origins: str = "*"

    # Security
    secret_key: str = "change-me-in-production-please"
    access_token_expire_minutes: int = 10080
    jwt_algorithm: str = "HS256"

    # Database
    database_url: str = ""
    auto_create_tables: bool = True

    # AI
    ai_provider: Literal["mock", "openai", "claude"] = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-5"
    # Default output ceiling per generation. Section-by-section report writing
    # keeps each call well under this; raised from the old 2048 so chapters are
    # not silently truncated.
    ai_max_tokens: int = 4096

    # ---- Scholarly references (real citations) ----
    references_enabled: bool = True
    reference_max: int = 40
    reference_timeout: int = 15
    reference_mailto: str = "support@researchai.app"

    # Payments
    payment_provider: Literal["paystack", "flutterwave"] = "paystack"
    paystack_secret_key: str = ""
    paystack_public_key: str = ""
    paystack_base_url: str = "https://api.paystack.co"
    flutterwave_secret_key: str = ""
    flutterwave_base_url: str = "https://api.flutterwave.com/v3"
    payment_callback_url: str = "http://localhost:8000/api/v1/payment/callback"
    # Where the payment callback sends the user's browser back to after we
    # verify the transaction (your Next.js app).
    frontend_url: str = "http://localhost:3000"
    default_currency: str = "GHS"
    # Paystack expects the amount in the currency's minor unit (pesewas for GHS,
    # kobo for NGN): multiply the cedi price by 100. GHS 50.00 -> 5_000.
    price_basic: int = 5_000      # GHS 50.00 / month
    price_premium: int = 12_000   # GHS 120.00 / month
    # Annual prices (two months free vs paying monthly).
    price_basic_annual: int = 50_000     # GHS 500.00 / year
    price_premium_annual: int = 120_000  # GHS 1,200.00 / year

    # Uploads
    upload_dir: str = "./storage/uploads"
    report_dir: str = "./storage/reports"
    max_upload_mb: int = 25

    # Optional
    redis_url: str = "redis://localhost:6379/0"

    @property
    def resolved_database_url(self) -> str:
        """Fall back to a local SQLite file when no DATABASE_URL is provided."""
        if self.database_url:
            return self.database_url
        return "sqlite:///./rai_core.db"

    @property
    def plan_prices(self) -> dict[str, int]:
        return {"basic": self.price_basic, "premium": self.price_premium}

    def price_for(self, plan: str, interval: str = "monthly") -> int:
        """Resolve the charge amount (minor units) for a plan + billing interval."""
        annual = {"basic": self.price_basic_annual, "premium": self.price_premium_annual}
        monthly = self.plan_prices
        table = annual if interval == "annual" else monthly
        if plan not in table:
            raise KeyError(plan)
        return table[plan]

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if raw in ("", "*"):
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    _INSECURE_SECRETS = {"", "change-me-in-production-please"}

    def production_problems(self) -> list[str]:
        """Fatal misconfigurations that must be resolved before going live.

        Returns an empty list outside production. In production it surfaces every
        insecure default so the app can refuse to boot rather than run unsafely.
        """
        if not self.is_production:
            return []
        problems: list[str] = []
        if self.secret_key in self._INSECURE_SECRETS or len(self.secret_key) < 32:
            problems.append(
                "SECRET_KEY must be a unique, random value of at least 32 chars "
                '(generate: python -c "import secrets; print(secrets.token_urlsafe(48))").'
            )
        if self.debug:
            problems.append("DEBUG must be false in production.")
        if self.auto_create_tables:
            problems.append(
                "AUTO_CREATE_TABLES must be false in production; apply Alembic "
                "migrations with `alembic upgrade head` instead."
            )
        if not self.database_url:
            problems.append("DATABASE_URL (PostgreSQL) must be set in production.")
        if self.cors_origin_list == ["*"]:
            problems.append(
                "CORS_ORIGINS must be an explicit comma-separated allowlist in "
                "production, not '*'."
            )
        if self.payment_provider == "paystack" and not self.paystack_secret_key:
            problems.append(
                "PAYSTACK_SECRET_KEY must be set in production so webhook "
                "signatures and transactions can be verified."
            )
        if self.ai_provider == "openai" and not self.openai_api_key:
            problems.append("OPENAI_API_KEY must be set when AI_PROVIDER=openai.")
        if self.ai_provider == "claude" and not self.anthropic_api_key:
            problems.append("ANTHROPIC_API_KEY must be set when AI_PROVIDER=claude.")
        return problems


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
