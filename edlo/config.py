from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    # --- environment ---
    environment: Literal["development", "test", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_format: Literal["console", "json"] = "console"
    # --- data ---
    database_url: str = "sqlite:///./edlo.db"
    # --- storage ---
    storage_backend: Literal["local", "s3"] = "local"
    upload_dir: Path = Path("./uploads")
    s3_bucket: str = ""
    s3_region: str = "us-east-1"
    s3_endpoint_url: str | None = None
    presign_upload_ttl_seconds: int = 900
    presign_download_ttl_seconds: int = 900
    max_upload_bytes: int = 500 * 1024 * 1024
    # --- queue ---
    queue_backend: Literal["rq", "sqs"] = "rq"
    redis_url: str = "redis://localhost:6379/0"
    sqs_queue_url: str = ""
    sqs_visibility_timeout_seconds: int = 300
    sqs_wait_time_seconds: int = 20
    # --- AI ---
    ai_enabled: bool = False
    model_provider: Literal["mock", "openai_compatible"] = "mock"
    model_name: str = ""
    model_base_url: str = ""
    model_api_key: str = ""
    model_timeout_seconds: int = 45
    prompt_cutlist_version: str = "cutlist-v1"
    prompt_pack_version: str = "pack-v1"
    max_cuts: int = 12
    max_cold_opens: int = 5
    # --- auth ---
    auth_mode: Literal["pilot_token", "oidc"] = "pilot_token"
    oidc_issuer: str = ""
    oidc_audience: str = ""
    jwks_cache_seconds: int = 3600
    # --- observability ---
    otel_enabled: bool = False
    otel_exporter_otlp_endpoint: str = ""
    metrics_namespace: str = "Edlo"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


"""@field_validator("user_api_keys", mode="before")
@classmethod
def parse_api_keys(cls, v):
    if isinstance(v, str):
        return json.loads(v)
    return v


@model_validator(mode="after")
def check_required_keys(self):
    required = {"albert", "chris", "paul"}
    missing = required - self.api_keys.keys()
    if missing:
        raise ValueError(f"Missing required api_keys: {missing}")
    return self"""
