import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("CCX_APP_NAME", "CCX Analysis Backend")
    version: str = os.getenv("CCX_VERSION", "0.1.0")
    environment: str = os.getenv("CCX_ENV", "development")
    host: str = os.getenv("CCX_HOST", "127.0.0.1")
    port: int = int(os.getenv("CCX_PORT", "18080"))
    reload: bool = _env_bool("CCX_RELOAD", False)


settings = Settings()
