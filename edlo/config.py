from functools import lru_cache
from pathlib import Path
from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore") 
    environment: str = "development"
    database_url: str = "sqlite:///./edlo.db"
    redis_url: str = "redis://localhost:6379/0"
    upload_dir: Path = Path("uploads")
    max_upload_bytes: int = 500 * 1024 * 1024
    ai_enabled: bool = False
    model_name: str = ""
    model_base_url: str | None = None
    model_api_key: SecretStr = SecretStr("")
    user_api_keys: dict[str, SecretStr]

@field_validator("user_api_keys", mode="before")
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
    return self

@lru_cache
def get_settings() -> Settings:
    settings = Settings() 
    settings.upload_dir.mkdir(parents=True, exist_ok=True) 
    return settings