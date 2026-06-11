from __future__ import annotations

import json
import csv
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.core.config import settings
from app.services.risk.ccx_adapter import detect_stress_unit, run_full_risk, stress_unit_to_pa_factor
from app.services.risk.ccx_metrics import extract_structural_metrics_from_h5
from app.services.risk.report_builder import build_risk_report

RiskStatus = Literal["queued", "running", "completed", "failed"]

_RISK_TASKS: dict[str, dict] = {}
_RISK_LOCK = threading.Lock()


class RiskTaskNotFound(LookupError):
    pass


def start_risk_task(task_id: str, preprocess_result: dict) -> dict:
    existing_task = _get_memory_task(task_id)
    if existing_task and existing_task.get("status") in {"queued", "running", "completed"}:
        return existing_task

    task_dir = _task_dir(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    tower_metadata = _tower_metadata(preprocess_result)
    task = {
        "task_id": task_id,
        "status": "queued",
        "stage": "risk",
        "stage_label": "等待执行有限元风险评估",
        "route_id": preprocess_result.get("route_id", ""),
        "tower_type": preprocess_result.get("tower_type", ""),
        "tower_shape": tower_metadata.get("shape", ""),
        "material": tower_metadata.get("material", ""),
        "inp_file": preprocess_result.get("inp_file", ""),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "message": "风险评估任务已创建",
        "progress": {"current": 0, "total": 0},
        "result_url": f"/api/risk/tasks/{task_id}/result",
    }
    _set_task(task_id, task)
    threading.Thread(target=_run_task, args=(task_id, preprocess_result, task_dir), daemon=True).start()
    return task


def get_risk_task(task_id: str) -> dict:
    task = _get_memory_task(task_id)
    if task is not None:
        return task

    result_path = _result_path(task_id)
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        return {
            "task_id": task_id,
            "status": result.get("status", "completed"),
            "stage": "risk",
            "stage_label": result.get("stage_label", "风险评估完成"),
            "route_id": result.get("route_id", ""),
            "tower_type": result.get("tower_type", ""),
            "tower_shape": result.get("tower_shape", ""),
            "material": result.get("material", ""),
            "inp_file": result.get("inp_file", ""),
            "created_at": result.get("created_at", ""),
            "updated_at": result.get("completed_at", ""),
            "message": result.get("message", "风险评估完成"),
            "progress": result.get("progress", {"current": 0, "total": 0}),
            "result_url": f"/api/risk/tasks/{task_id}/result",
        }

    raise RiskTaskNotFound(task_id)


def get_risk_result(task_id: str) -> dict:
    result_path = _result_path(task_id)
    if not result_path.exists():
        raise RiskTaskNotFound(task_id)
    result = json.loads(result_path.read_text(encoding="utf-8"))
    _ensure_rainfall_cases(result)
    _ensure_structural_metrics(result)
    return _normalize_result_units(result)


def get_risk_stress_h5_path(task_id: str, case: str = "base") -> Path:
    result = get_risk_result(task_id)
    h5_path = ""
    if case == "base":
        h5_path = result.get("base", {}).get("h5_path", "")
    else:
        cases = result.get("full", {}).get("summary", {}).get("cases", [])
        for item in cases:
            if item.get("case") == case:
                h5_path = item.get("h5_path", "")
                break
    if not h5_path:
        raise RiskTaskNotFound(f"Risk h5 not found for task: {task_id}, case: {case}")

    path = Path(h5_path)
    if not path.exists():
        raise RiskTaskNotFound(f"Risk h5 file not found: {path}")
    return path


def _run_task(task_id: str, preprocess_result: dict, task_dir: Path) -> None:
    _update_task(task_id, status="running", stage_label="正在执行有限元风险评估", message="正在扫描降雨工况", progress={"current": 0, "total": 0})
    try:
        def on_progress(result_item: object, row: dict, current: int, total: int) -> None:
            label = row.get("label") or row.get("case") or "风险工况"
            _update_task(
                task_id,
                status="running",
                stage_label="正在执行完整风险评估",
                message=f"正在计算 {label} ({current}/{total})",
                progress={"current": current, "total": total},
            )

        risk = run_full_risk(preprocess_result, task_dir / "worst", progress=on_progress)
        base_result = risk["base"]
        report = build_risk_report(base_result)
        if risk.get("summary"):
            report = build_risk_report(base_result, risk["summary"])
        tower_metadata = _tower_metadata(preprocess_result)
        result = {
            "task_id": task_id,
            "status": "completed",
            "stage_label": "风险评估完成",
            "message": "风险评估完成",
            "route_id": preprocess_result.get("route_id", ""),
            "tower_type": preprocess_result.get("tower_type", ""),
            "tower_shape": tower_metadata.get("shape", ""),
            "material": tower_metadata.get("material", ""),
            "inp_file": preprocess_result.get("inp_file", ""),
            "created_at": get_risk_task(task_id).get("created_at", ""),
            "completed_at": _now_iso(),
            "base": base_result,
            "full": {
                "summary_csv": risk.get("summary_csv", ""),
                "case_count": risk.get("case_count", 0),
                "rainfall_data_dir": risk.get("rainfall_data_dir", ""),
                "summary": risk.get("summary", {}),
            },
            "progress": {"current": risk.get("case_count", 0), "total": risk.get("case_count", 0)},
            "report": report,
        }
        _result_path(task_id).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _update_task(
            task_id,
            status="completed",
            stage_label="风险评估完成",
            message="风险评估完成",
            progress={"current": risk.get("case_count", 0), "total": risk.get("case_count", 0)},
        )
    except Exception as error:  # noqa: BLE001 - risk failure must be visible to the frontend.
        tower_metadata = _tower_metadata(preprocess_result)
        failure = {
            "task_id": task_id,
            "status": "failed",
            "stage_label": "风险评估失败",
            "message": str(error),
            "route_id": preprocess_result.get("route_id", ""),
            "tower_type": preprocess_result.get("tower_type", ""),
            "tower_shape": tower_metadata.get("shape", ""),
            "material": tower_metadata.get("material", ""),
            "inp_file": preprocess_result.get("inp_file", ""),
            "completed_at": _now_iso(),
        }
        _result_path(task_id).write_text(
            json.dumps(failure, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _update_task(task_id, status="failed", stage_label="风险评估失败", message=str(error))


def _task_dir(task_id: str) -> Path:
    return settings.ccx_results_dir / task_id


def _result_path(task_id: str) -> Path:
    return _task_dir(task_id) / "risk_result.json"


def _tower_metadata(preprocess_result: dict) -> dict[str, str]:
    metadata = preprocess_result.get("environment", {}).get("metadata", {})
    if not isinstance(metadata, dict):
        return {}

    result = {}
    for key in ("shape", "material"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            result[key] = value.strip()
    return result


def _ensure_rainfall_cases(result: dict) -> None:
    summary = result.get("full", {}).get("summary")
    if not isinstance(summary, dict) or summary.get("cases"):
        return

    summary_csv = result.get("full", {}).get("summary_csv")
    if not summary_csv or not Path(summary_csv).exists():
        return

    unit = summary.get("stress_unit") or detect_stress_unit(result.get("inp_file", ""))
    factor = summary.get("stress_unit_factor_to_pa") or stress_unit_to_pa_factor(unit)
    stress_limit = result.get("base", {}).get("stress_limit_pa") or 315_000_000.0
    cases = []
    with Path(summary_csv).open("r", encoding="utf-8-sig", errors="ignore", newline="") as file:
        for row in csv.DictReader(file):
            stress_pa = _float_or_none(row.get("max_abs_stress"))
            stress_pa = stress_pa * factor if stress_pa is not None else None
            risk_index = stress_pa / stress_limit if stress_pa is not None and stress_limit else None
            cases.append(
                {
                    "case": row.get("case", ""),
                    "label": row.get("label", ""),
                    "rainfall_mm": _float_or_none(row.get("rainfall_mm")),
                    "day": _int_or_none(row.get("day")),
                    "max_abs_stress_pa": stress_pa,
                    "risk_index": risk_index,
                    "stress_over_limit": bool(risk_index is not None and risk_index > 1),
                    "h5_path": row.get("h5", ""),
                    **extract_structural_metrics_from_h5(row.get("h5", "")),
                }
            )

    summary["cases"] = sorted(cases, key=lambda case: ((case.get("rainfall_mm") or 0), (case.get("day") or 0), case.get("case") or ""))


def _ensure_structural_metrics(result: dict) -> None:
    base = result.get("base")
    if isinstance(base, dict):
        _merge_structural_metrics(base, str(base.get("h5_path", "")))

    summary = result.get("full", {}).get("summary")
    if not isinstance(summary, dict):
        return

    cases = summary.get("cases")
    if isinstance(cases, list):
        for item in cases:
            if isinstance(item, dict):
                _merge_structural_metrics(item, str(item.get("h5_path", "")))

    over_limit_cases = summary.get("over_limit_cases")
    if isinstance(over_limit_cases, list):
        for item in over_limit_cases:
            if isinstance(item, dict):
                _merge_structural_metrics(item, str(item.get("h5_path", "")))

    max_case = summary.get("max_case")
    if isinstance(max_case, dict):
        _merge_structural_metrics(max_case, str(max_case.get("h5_path", "")))


def _merge_structural_metrics(target: dict, h5_path: str) -> None:
    if "tower_tilt_deg" in target and "max_abs_strain_micro" in target:
        return
    target.update(extract_structural_metrics_from_h5(h5_path))


def _float_or_none(value: object) -> float | None:
    try:
        return None if value in {None, ""} else float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int_or_none(value: object) -> int | None:
    parsed = _float_or_none(value)
    return None if parsed is None else int(parsed)


def _get_memory_task(task_id: str) -> dict | None:
    with _RISK_LOCK:
        task = _RISK_TASKS.get(task_id)
        return dict(task) if task is not None else None


def _set_task(task_id: str, task: dict) -> None:
    with _RISK_LOCK:
        _RISK_TASKS[task_id] = dict(task)


def _update_task(task_id: str, **values: object) -> None:
    with _RISK_LOCK:
        task = _RISK_TASKS.get(task_id)
        if task is None:
            return
        task.update(values)
        task["updated_at"] = _now_iso()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _normalize_result_units(result: dict) -> dict:
    base = result.get("base")
    if not isinstance(base, dict):
        return result

    if base.get("stress_unit"):
        return result

    stress_unit = detect_stress_unit(str(result.get("inp_file", "")))
    factor = stress_unit_to_pa_factor(stress_unit)
    max_stress_raw = _float_or_none(base.get("max_stress"))
    max_abs_stress_raw = _float_or_none(base.get("max_abs_stress"))
    max_stress_pa = max_stress_raw * factor if max_stress_raw is not None else None
    max_abs_stress_pa = max_abs_stress_raw * factor if max_abs_stress_raw is not None else None
    stress_limit_pa = 315_000_000.0

    base["stress_unit"] = stress_unit
    base["stress_unit_factor_to_pa"] = factor
    base["max_stress_raw"] = max_stress_raw
    base["max_abs_stress_raw"] = max_abs_stress_raw
    base["max_stress"] = max_stress_pa
    base["max_abs_stress"] = max_abs_stress_pa
    base["max_stress_pa"] = max_stress_pa
    base["max_abs_stress_pa"] = max_abs_stress_pa
    base["stress_limit_pa"] = stress_limit_pa
    base["risk_index"] = (max_abs_stress_pa / stress_limit_pa) if max_abs_stress_pa is not None else None
    result["report"] = build_risk_report(base)
    return result


def _float_or_none(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
