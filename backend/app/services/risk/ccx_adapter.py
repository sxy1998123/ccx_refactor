from __future__ import annotations

import importlib.util
import csv
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Any

from app.core.config import settings
from app.services.risk.ccx_metrics import extract_structural_metrics_from_h5

INP_BY_TOWER_TYPE = {
    "guxing": "Guxing_tower-m-9B-Pa.inp",
    "jiubei": "Jiubei_tower-mm-2B-MPa.inp",
    "maotouying": "Maotouyin_tower-mm-14B-MPa.inp",
}

STRESS_LIMIT_PA = 315_000_000.0


class CcxAdapterError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_core() -> ModuleType:
    core_path = settings.ccx_root / "core.py"
    if not core_path.exists():
        raise CcxAdapterError(f"CCX core.py not found: {core_path}")

    spec = importlib.util.spec_from_file_location("ccx_vendor_core", core_path)
    if spec is None or spec.loader is None:
        raise CcxAdapterError(f"Unable to load CCX core module: {core_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def resolve_inp_path(tower_type: str, inp_file: str) -> Path:
    inp_name = Path(inp_file).name if inp_file else INP_BY_TOWER_TYPE.get(tower_type, "")
    if not inp_name:
        raise CcxAdapterError(f"Unsupported tower type: {tower_type}")

    inp_path = settings.ccx_root / inp_name
    if not inp_path.exists():
        raise CcxAdapterError(f"CCX inp template not found: {inp_path}")
    return inp_path


def run_full_risk(
    preprocess_result: dict[str, Any],
    out_dir: Path,
    progress: Any | None = None,
) -> dict[str, Any]:
    core = load_core()
    inp_path = resolve_inp_path(
        str(preprocess_result.get("tower_type", "")),
        str(preprocess_result.get("inp_file", "")),
    )
    displacement = _read_displacement(preprocess_result)
    out_dir.mkdir(parents=True, exist_ok=True)

    data_dir = settings.ccx_rainfall_data_dir
    if not data_dir.exists():
        raise CcxAdapterError(f"CCX rainfall data directory not found: {data_dir}")

    total_cases = 1 + len(core.scan_worst_displacement_cases(data_dir))

    def on_progress(result: Any, row: dict[str, Any]) -> None:
        if progress is not None:
            progress(result, row, len(completed_rows) + 1, total_cases)
        completed_rows.append(row)

    completed_rows: list[dict[str, Any]] = []
    results, summary_csv = core.run_worst_case_directory(
        inp_path=inp_path,
        base_displacement=core.Displacement(
            x=displacement["x"],
            y=displacement["y"],
            z=displacement["z"],
        ),
        out_dir=out_dir,
        data_dir=data_dir,
        progress=on_progress,
    )

    summary_rows = _read_summary_rows(summary_csv)
    base_result = results[0]
    base_row = summary_rows[0] if summary_rows else {}
    return {
        "base": _normalize_result(base_result, base_row, inp_path, displacement),
        "summary_csv": str(summary_csv),
        "case_count": len(results),
        "rainfall_data_dir": str(data_dir),
        "summary": _summarize_rainfall(summary_rows, inp_path),
    }


def run_base_risk(preprocess_result: dict[str, Any], out_dir: Path) -> dict[str, Any]:
    core = load_core()
    inp_path = resolve_inp_path(
        str(preprocess_result.get("tower_type", "")),
        str(preprocess_result.get("inp_file", "")),
    )
    displacement = _read_displacement(preprocess_result)
    out_dir.mkdir(parents=True, exist_ok=True)

    result = core.run_base_case(
        inp_path=inp_path,
        base_displacement=core.Displacement(
            x=displacement["x"],
            y=displacement["y"],
            z=displacement["z"],
        ),
        out_dir=out_dir,
    )
    return _normalize_result(result, {}, inp_path, displacement)


def _normalize_result(result: Any, row: dict[str, Any], inp_path: Path, displacement: dict[str, float]) -> dict[str, Any]:
    stress = result.stress
    stress_unit = detect_stress_unit(inp_path)
    stress_factor = stress_unit_to_pa_factor(stress_unit)
    max_stress_raw = _float_or_none(row.get("max_stress")) if row else _float_or_none(getattr(stress, "value", None))
    max_abs_stress_raw = _float_or_none(row.get("max_abs_stress")) if row else _float_or_none(getattr(stress, "abs_value", None))
    max_stress_pa = max_stress_raw * stress_factor if max_stress_raw is not None else None
    max_abs_stress_pa = max_abs_stress_raw * stress_factor if max_abs_stress_raw is not None else None
    risk_index = (max_abs_stress_pa / STRESS_LIMIT_PA) if max_abs_stress_pa is not None else None
    h5_path = str(result.h5_path or "")
    structural_metrics = extract_structural_metrics_from_h5(h5_path)

    return {
        "case": result.case_name,
        "inp_path": str(result.inp_path),
        "h5_path": h5_path,
        "summary_csv": str(result.csv_path),
        "solver_log": str(result.solver_log_path or ""),
        "log": str(result.log_path),
        "returncode": result.returncode,
        "applied_displacement_m": displacement,
        "stress_unit": stress_unit,
        "stress_unit_factor_to_pa": stress_factor,
        "max_stress_raw": max_stress_raw,
        "max_abs_stress_raw": max_abs_stress_raw,
        "max_stress": max_stress_pa,
        "max_abs_stress": max_abs_stress_pa,
        "max_stress_pa": max_stress_pa,
        "max_abs_stress_pa": max_abs_stress_pa,
        "stress_limit_pa": STRESS_LIMIT_PA,
        "risk_index": risk_index,
        "stress_element": getattr(stress, "element_label", None),
        "stress_component": getattr(stress, "component", None),
        "stress_error": getattr(stress, "error", ""),
        **structural_metrics,
    }


def _read_summary_rows(summary_csv: str | Path) -> list[dict[str, str]]:
    with Path(summary_csv).open("r", encoding="utf-8-sig", errors="ignore", newline="") as file:
        return list(csv.DictReader(file))


def _summarize_rainfall(rows: list[dict[str, str]], inp_path: Path) -> dict[str, Any]:
    stress_unit = detect_stress_unit(inp_path)
    factor = stress_unit_to_pa_factor(stress_unit)
    cases = []
    first_damage_by_rainfall: dict[float, int] = {}
    max_case: dict[str, Any] | None = None

    for row in rows:
        rainfall = _float_or_none(row.get("rainfall_mm"))
        day = _int_or_none(row.get("day"))
        raw_abs = _float_or_none(row.get("max_abs_stress"))
        stress_pa = raw_abs * factor if raw_abs is not None else None
        risk_index = stress_pa / STRESS_LIMIT_PA if stress_pa is not None else None
        is_over = bool(risk_index is not None and risk_index > 1)
        h5_path = row.get("h5", "")
        structural_metrics = extract_structural_metrics_from_h5(h5_path)
        case = {
            "case": row.get("case", ""),
            "label": row.get("label", ""),
            "rainfall_mm": rainfall,
            "day": day,
            "max_abs_stress_pa": stress_pa,
            "risk_index": risk_index,
            "stress_over_limit": is_over,
            "h5_path": h5_path,
            **structural_metrics,
        }
        cases.append(case)

        if risk_index is not None and (max_case is None or risk_index > (max_case.get("risk_index") or -1)):
            max_case = case

        if is_over and rainfall is not None and day is not None and day > 0:
            if rainfall not in first_damage_by_rainfall or day < first_damage_by_rainfall[rainfall]:
                first_damage_by_rainfall[rainfall] = day

    damage_conclusions = [
        {"rainfall_mm": rainfall, "day": day, "text": f"{rainfall:g}mm连续{day}d损坏"}
        for rainfall, day in sorted(first_damage_by_rainfall.items())
    ]

    return {
        "stress_unit": stress_unit,
        "stress_unit_factor_to_pa": factor,
        "case_count": len(cases),
        "cases": sorted(cases, key=lambda case: ((case.get("rainfall_mm") or 0), (case.get("day") or 0), case.get("case") or "")),
        "max_case": max_case,
        "over_limit_cases": [case for case in cases if case["stress_over_limit"]],
        "damage_conclusions": damage_conclusions,
        "damage_conclusions_text": "；".join(item["text"] for item in damage_conclusions) if damage_conclusions else "无",
    }


def detect_stress_unit(inp_path: str | Path) -> str:
    name = Path(inp_path).stem.lower()
    if "mpa" in name:
        return "MPa"
    if "pa" in name:
        return "Pa"
    return "Pa"


def stress_unit_to_pa_factor(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized == "mpa":
        return 1_000_000.0
    if normalized == "kpa":
        return 1_000.0
    return 1.0


def _read_displacement(preprocess_result: dict[str, Any]) -> dict[str, float]:
    displacement = preprocess_result.get("tower_summary", {}).get("ccx_displacement_m", {})
    values = {
        "x": _float_or_none(displacement.get("x")),
        "y": _float_or_none(displacement.get("y")),
        "z": _float_or_none(displacement.get("z")),
    }
    if any(value is None for value in values.values()):
        raise CcxAdapterError("Preprocess result does not contain complete ccx_displacement_m")
    return {key: float(value) for key, value in values.items() if value is not None}


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    number = _float_or_none(value)
    return int(number) if number is not None else None
