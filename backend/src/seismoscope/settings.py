from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    waveform_storage_path: str = "/data/waveforms"
    usgs_event_base_url: str = "https://earthquake.usgs.gov"
    earthscope_base_url: str = "https://service.earthscope.org"
    log_level: str = "INFO"
    worker_poll_seconds: int = 3


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
