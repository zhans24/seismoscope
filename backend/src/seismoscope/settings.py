from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    redis_url: str = "redis://redis:6379/0"
    waveform_storage_path: str = "/data/waveforms"
    usgs_event_base_url: str = "https://earthquake.usgs.gov"
    earthscope_base_url: str = "https://service.earthscope.org"
    log_level: str = "INFO"
    worker_poll_seconds: int = 3
    cache_lock_seconds: int = 50
    event_cache_ttl_seconds: int = 300
    historical_event_cache_ttl_seconds: int = 86400
    station_cache_ttl_seconds: int = 3600
    plate_cache_ttl_seconds: int = 86400
    stale_cache_ttl_seconds: int = 604800


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
