import json
from functools import lru_cache
from typing import Annotated

from pydantic import AliasChoices, Field, PositiveFloat, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    log_level: str = "INFO"
    model_version: str = "phase2-v1"
    database_url: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/ufc_analysis"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    api_key: str | None = None
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://localhost:3000"],
        validation_alias=AliasChoices("CORS_ORIGINS", "CORS_ALLOWED_ORIGINS"),
    )
    elo_initial_rating: float = 1500.0
    elo_k_factor: float = 32.0
    elo_method_multiplier: float = 1.0
    elo_dominance_multiplier: float = 1.0
    elo_context_multiplier: float = 1.0
    recency_half_life_days: float = 730.0
    minimum_opponent_sample: int = 3
    phase3_random_seed: int = 42
    phase3_artifact_dir: str = "artifacts"
    odds_api_key: str | None = None
    odds_api_base_url: str = "https://api.the-odds-api.com"
    odds_api_regions: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["au"])
    odds_api_markets: str = "h2h"
    odds_api_odds_format: str = "decimal"
    odds_api_date_format: str = "iso"
    odds_api_timeout_seconds: PositiveFloat = 20
    odds_api_max_retries: int = Field(default=3, ge=0)
    odds_api_stale_after_minutes: int = Field(default=30, ge=1)
    odds_api_low_quota_warning: int = Field(default=100, ge=0)
    odds_api_sport_key: str | None = None
    odds_event_match_tolerance_hours: PositiveFloat = 24
    context_engine_enabled: bool = True
    context_max_individual_adjustment: float = Field(default=0.02, ge=0, le=1)
    context_max_category_adjustment: float = Field(default=0.03, ge=0, le=1)
    context_max_total_adjustment: float = Field(default=0.05, ge=0, le=1)
    context_min_auto_approval_confidence: float = Field(default=0.90, ge=0, le=1)
    context_min_auto_approval_source_reliability: float = Field(default=0.90, ge=0, le=1)
    context_default_match_tolerance_hours: PositiveFloat = 48
    context_require_review_for_injury: bool = True
    context_require_review_for_subjective_signals: bool = True
    context_recency_decay_enabled: bool = True

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_database_url(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgres://"):
            return "postgresql+psycopg2://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+psycopg2://" + value.removeprefix("postgresql://")
        return value

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("odds_api_regions", mode="before")
    @classmethod
    def parse_odds_regions(cls, value: object) -> object:
        if isinstance(value, str):
            if value.lstrip().startswith("["):
                return json.loads(value)
            return [region.strip() for region in value.split(",") if region.strip()]
        return value

    @model_validator(mode="after")
    def validate_context_caps(self) -> "Settings":
        if self.context_max_individual_adjustment > self.context_max_category_adjustment:
            raise ValueError("CONTEXT_MAX_INDIVIDUAL_ADJUSTMENT cannot exceed the category cap")
        if self.context_max_category_adjustment > self.context_max_total_adjustment:
            raise ValueError("CONTEXT_MAX_CATEGORY_ADJUSTMENT cannot exceed the total cap")
        if self.app_env.lower() == "production":
            if "localhost" in self.database_url:
                raise ValueError("DATABASE_URL must be explicitly configured for production")
            if not self.api_key:
                raise ValueError("API_KEY is required in production")
            if not self.odds_api_key:
                raise ValueError("ODDS_API_KEY is required in production for upcoming UFC ingestion")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
