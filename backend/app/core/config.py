import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _backend_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def _database_path() -> Path:
    configured_path = os.getenv("CCX_DATABASE_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return (_backend_root() / "data" / "ccx.sqlite3").resolve()


def _data_dir() -> Path:
    configured_path = os.getenv("CCX_DATA_DIR")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return (_backend_root() / "data").resolve()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("CCX_APP_NAME", "CCX Analysis Backend")
    version: str = os.getenv("CCX_VERSION", "0.1.0")
    environment: str = os.getenv("CCX_ENV", "development")
    host: str = os.getenv("CCX_HOST", "127.0.0.1")
    port: int = int(os.getenv("CCX_PORT", "18080"))
    reload: bool = _env_bool("CCX_RELOAD", False)
    data_dir: Path = field(default_factory=_data_dir)
    database_path: Path = field(default_factory=_database_path)


settings = Settings()
