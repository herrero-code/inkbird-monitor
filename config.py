from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    tuya_device_id: str
    tuya_local_key: str
    tuya_device_ip: str
    tuya_version: float = 3.3
    poll_interval_seconds: int = 3


settings = Settings()
