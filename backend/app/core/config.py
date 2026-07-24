import os
import sys
from dataclasses import dataclass, field
from pathlib import Path


def _env_bool(name: str, default: bool = False) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value.strip())
    except ValueError:
        return default


def _backend_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[2]


def _pyinstaller_root() -> Path | None:
    bundle_root = getattr(sys, "_MEIPASS", None)
    if not bundle_root:
        return None
    return Path(bundle_root).resolve()


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


def _base_stress_h5_path() -> Path:
    configured_path = os.getenv("CCX_BASE_STRESS_H5")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return Path(
        r"D:\Project2026\ccx_refactor_back\ccx(2)\results\codex_frontend_xyz_worst_h5py\Guxing_tower-m-9B-Pa_baseFE_C.h5",
    )


def _ccx_root() -> Path:
    configured_path = os.getenv("CCX_SOLVER_ROOT")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    candidates: list[Path] = []

    # 1) PyInstaller bundle: _MEIPASS / app/vendor/ccx (data copied by --add-data)
    bundle_root = _pyinstaller_root()
    if bundle_root is not None:
        candidates.extend(
            [
                bundle_root / "app" / "vendor" / "ccx",
                bundle_root / "vendor" / "ccx",
            ],
        )

    # 2) Relative to backend.exe (development / unpackaged)
    candidates.extend(
        [
            _backend_root() / "app" / "vendor" / "ccx",
            _backend_root() / "vendor" / "ccx",
        ],
    )

    # 3) CWD fallback
    candidates.extend(
        [
            Path.cwd() / "app" / "vendor" / "ccx",
            Path.cwd() / "vendor" / "ccx",
        ],
    )

    for candidate in candidates:
        if (candidate / "core.py").exists() and (candidate / "ccx" / "ccx.exe").exists():
            return candidate.resolve()

    if candidates:
        return candidates[0].resolve()
    return Path("app/vendor/ccx").resolve()


def _ccx_results_dir() -> Path:
    configured_path = os.getenv("CCX_RESULTS_DIR")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return (_data_dir() / "risk").resolve()


def _ccx_rainfall_data_dir() -> Path:
    configured_path = os.getenv("CCX_RAINFALL_DATA_DIR")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    return (_ccx_root() / "数据").resolve()


def _hazard_excel_path() -> Path:
    configured_path = os.getenv("CCX_HAZARD_EXCEL_PATH")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    candidates = [_backend_root() / "app" / "db" / "excel" / "data.xlsx"]
    bundle_root = _pyinstaller_root()
    if bundle_root is not None:
        candidates.append(bundle_root / "app" / "db" / "excel" / "data.xlsx")

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("CCX_APP_NAME", "杆塔失稳风险快速评估系统")
    version: str = os.getenv("CCX_VERSION", "0.1.0")
    environment: str = os.getenv("CCX_ENV", "development")
    host: str = os.getenv("CCX_HOST", "127.0.0.1")
    port: int = int(os.getenv("CCX_PORT", "18080"))
    reload: bool = _env_bool("CCX_RELOAD", False)
    data_dir: Path = field(default_factory=_data_dir)
    database_path: Path = field(default_factory=_database_path)
    base_stress_h5_path: Path = field(default_factory=_base_stress_h5_path)
    ccx_root: Path = field(default_factory=_ccx_root)
    ccx_results_dir: Path = field(default_factory=_ccx_results_dir)
    ccx_rainfall_data_dir: Path = field(default_factory=_ccx_rainfall_data_dir)
    ccx_rainfall_displacement_scale: float = _env_float("CCX_RAINFALL_DISPLACEMENT_SCALE", 0.8) # 应力位移缩放系数
    hazard_excel_path: Path = field(default_factory=_hazard_excel_path)


settings = Settings()
