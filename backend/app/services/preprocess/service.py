from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from app.core.config import settings
from app.services.preprocess.geologic import process_geologic_env
from app.services.preprocess.settlement import process_tower_txt

TaskStatus = Literal["queued", "running", "completed", "failed"]

_TASKS: dict[str, dict] = {}
_TASK_LOCK = threading.Lock()


class PreprocessTaskNotFound(LookupError):
    pass


def submit_preprocess_task(payload: dict) -> dict:
    task_id = f"pre-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    task_dir = _task_dir(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)

    task = {
        "task_id": task_id,
        "status": "queued",
        "route_id": payload["route_id"],
        "tower_type": payload["tower_type"],
        "inp_file": payload.get("inp_file", ""),
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "message": "预处理任务已创建",
        "result_url": f"/api/preprocess/tasks/{task_id}/result",
    }
    _set_task(task_id, task)
    threading.Thread(target=_run_task, args=(task_id, payload, task_dir), daemon=True).start()
    return task


def get_preprocess_task(task_id: str) -> dict:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is not None:
            return dict(task)

    result_path = _result_path(task_id)
    if result_path.exists():
        result = json.loads(result_path.read_text(encoding="utf-8"))
        return {
            "task_id": task_id,
            "status": result.get("status", "completed"),
            "route_id": result.get("route_id", ""),
            "tower_type": result.get("tower_type", ""),
            "inp_file": result.get("inp_file", ""),
            "created_at": result.get("created_at", ""),
            "updated_at": result.get("completed_at", ""),
            "message": result.get("message", "预处理完成"),
            "result_url": f"/api/preprocess/tasks/{task_id}/result",
        }

    raise PreprocessTaskNotFound(task_id)


def get_preprocess_result(task_id: str) -> dict:
    result_path = _result_path(task_id)
    if not result_path.exists():
        raise PreprocessTaskNotFound(task_id)

    return json.loads(result_path.read_text(encoding="utf-8"))


def _run_task(task_id: str, payload: dict, task_dir: Path) -> None:
    _update_task(task_id, status="running", message="正在处理塔基端与探地端 TXT 文件")
    try:
        tower_results = {
            key: process_tower_txt(file_path)
            for key, file_path in payload["tower_txt_files"].items()
        }
        environment = process_geologic_env(payload["env_txt_file"])
        result = {
            "task_id": task_id,
            "status": "completed",
            "message": "预处理完成",
            "route_id": payload["route_id"],
            "tower_type": payload["tower_type"],
            "inp_file": payload.get("inp_file", ""),
            "created_at": get_preprocess_task(task_id).get("created_at", ""),
            "completed_at": _now_iso(),
            "inputs": {
                "tower_txt_files": payload["tower_txt_files"],
                "env_txt_file": payload["env_txt_file"],
                "image_files": payload.get("image_files", []),
                "point_cloud_files": payload.get("point_cloud_files", []),
            },
            "environment": environment,
            "tower_results": tower_results,
            "tower_summary": _summarize_towers(tower_results),
        }
        _result_path(task_id).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _update_task(task_id, status="completed", message="预处理完成")
    except Exception as error:  # noqa: BLE001 - persisted task failure should include the concrete cause.
        failure = {
            "task_id": task_id,
            "status": "failed",
            "message": str(error),
            "route_id": payload.get("route_id", ""),
            "tower_type": payload.get("tower_type", ""),
            "inp_file": payload.get("inp_file", ""),
            "completed_at": _now_iso(),
        }
        _result_path(task_id).write_text(
            json.dumps(failure, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _update_task(task_id, status="failed", message=str(error))


def _summarize_towers(tower_results: dict[str, dict]) -> dict:
    drift_rows = []
    lat_values = []
    lon_values = []
    alt_values = []
    drift_values_m = {"x": [], "y": [], "z": []}
    drift_values_mm = {"x": [], "y": [], "z": []}

    for key, result in tower_results.items():
        imu = result.get("imu", {})
        gnss = result.get("gnss", {})
        total_drift = imu.get("total_drift_mm")
        for axis in ("x", "y", "z"):
            drift_m = imu.get(f"{axis}_drift_m")
            drift_mm = imu.get(f"{axis}_drift_mm")
            if drift_m is not None:
                drift_values_m[axis].append(float(drift_m))
            if drift_mm is not None:
                drift_values_mm[axis].append(float(drift_mm))

        if total_drift is not None:
            drift_rows.append(
                {
                    "slot": key,
                    "file_name": result.get("file_name", ""),
                    "total_drift_mm": total_drift,
                    "x_drift_m": imu.get("x_drift_m"),
                    "y_drift_m": imu.get("y_drift_m"),
                    "z_drift_m": imu.get("z_drift_m"),
                    "x_drift_mm": imu.get("x_drift_mm"),
                    "y_drift_mm": imu.get("y_drift_mm"),
                    "z_drift_mm": imu.get("z_drift_mm"),
                }
            )

        for source, values in ((gnss.get("mean_lat"), lat_values), (gnss.get("mean_lon"), lon_values), (gnss.get("mean_alt_m"), alt_values)):
            if source is not None:
                values.append(float(source))

    max_drift = max(drift_rows, key=lambda item: item["total_drift_mm"], default=None)
    return {
        "tower_count": len(tower_results),
        "mean_lat": _mean_or_none(lat_values),
        "mean_lon": _mean_or_none(lon_values),
        "mean_alt_m": _mean_or_none(alt_values),
        "max_total_drift_mm": max_drift["total_drift_mm"] if max_drift else None,
        "max_drift_source": max_drift["file_name"] if max_drift else "",
        "max_drift_slot": max_drift["slot"] if max_drift else "",
        "ccx_displacement_m": {
            "x": _mean_or_none(drift_values_m["x"]),
            "y": _mean_or_none(drift_values_m["y"]),
            "z": _mean_or_none(drift_values_m["z"]),
        },
        "ccx_displacement_mm": {
            "x": _mean_or_none(drift_values_mm["x"]),
            "y": _mean_or_none(drift_values_mm["y"]),
            "z": _mean_or_none(drift_values_mm["z"]),
        },
    }


def _mean_or_none(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _task_dir(task_id: str) -> Path:
    return settings.data_dir / "preprocess" / task_id


def _result_path(task_id: str) -> Path:
    return _task_dir(task_id) / "result.json"


def _set_task(task_id: str, task: dict) -> None:
    with _TASK_LOCK:
        _TASKS[task_id] = dict(task)


def _update_task(task_id: str, **values: object) -> None:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return
        task.update(values)
        task["updated_at"] = _now_iso()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
