from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

MAX_SERIES_POINTS = 2000


def _parse_utc_time(time_text: str) -> datetime:
    time_text = time_text.strip()
    if "." in time_text:
        main, frac = time_text.split(".", 1)
        parsed = datetime.strptime(main, "%Y%m%d%H%M%S")
        microsecond = int((frac + "000000")[:6])
        return parsed.replace(microsecond=microsecond, tzinfo=timezone.utc)

    return datetime.strptime(time_text, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def _format_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S") + f".{value.microsecond // 1000:03d}"


def _parse_line(line: str) -> tuple[datetime | None, dict[str, dict[str, float | str]]]:
    line = line.replace("\x00", " ")
    line = re.sub(r"([A-Za-z%/])time:", r"\1 time:", line).strip()
    if not line:
        return None, {}

    time_match = re.search(r"time:(\d{14}(?:\.\d+)?)", line)
    if not time_match:
        return None, {}

    try:
        parsed_time = _parse_utc_time(time_match.group(1))
    except ValueError:
        return None, {}

    metrics: dict[str, dict[str, float | str]] = {}
    metric_pattern = re.compile(r"([A-Za-z]+):\s*([-+]?\d+(?:\.\d+)?)\s*([A-Za-z%/]+)?")
    for name, value, unit in metric_pattern.findall(line):
        if name in {"time", "Lat", "Lon"}:
            continue
        try:
            metrics[name] = {"value": float(value), "unit": unit or ""}
        except ValueError:
            continue

    return parsed_time, metrics


def process_geologic_env(env_txt_path: str | Path) -> dict:
    source_path = Path(env_txt_path)
    values_by_name: dict[str, list[float]] = defaultdict(list)
    series_by_name: dict[str, list[tuple[datetime, float]]] = defaultdict(list)
    units_by_name: dict[str, str] = {}
    timestamps: list[datetime] = []

    with source_path.open("r", encoding="utf-8", errors="ignore") as file:
        for line in file:
            parsed_time, metrics = _parse_line(line)
            if parsed_time is None or parsed_time.year == 2000:
                continue

            timestamps.append(parsed_time)
            for name, info in metrics.items():
                value = float(info["value"])
                values_by_name[name].append(value)
                series_by_name[name].append((parsed_time, value))
                units_by_name.setdefault(name, str(info["unit"]))

    if not timestamps:
        raise ValueError(f"No valid geologic records found in {source_path}")

    metrics_result = {}
    for name in sorted(values_by_name):
        values = values_by_name[name]
        if not values:
            continue
        metrics_result[name] = {
            "value": sum(values) / len(values),
            "unit": units_by_name.get(name, ""),
            "count": len(values),
            "series": _downsample_time_series(series_by_name[name], MAX_SERIES_POINTS),
        }

    return {
        "source_file": str(source_path),
        "start_time": _format_time(min(timestamps)),
        "end_time": _format_time(max(timestamps)),
        "record_count": len(timestamps),
        "metrics": metrics_result,
    }


def _downsample_time_series(points: list[tuple[datetime, float]], max_points: int) -> list[dict[str, float | str]]:
    if not points:
        return []

    points.sort(key=lambda item: item[0])
    if len(points) <= max_points:
        return [{"time": _format_time(time), "value": value} for time, value in points]

    buckets = [
        {"time_sum": 0.0, "value_sum": 0.0, "count": 0}
        for _ in range(max_points)
    ]
    base_time = points[0][0]
    total = len(points)
    for index, (time, value) in enumerate(points):
        bucket_index = min(max_points - 1, index * max_points // total)
        bucket = buckets[bucket_index]
        bucket["time_sum"] += (time - base_time).total_seconds()
        bucket["value_sum"] += value
        bucket["count"] += 1

    result = []
    for bucket in buckets:
        count = bucket["count"]
        if not count:
            continue
        seconds = bucket["time_sum"] / count
        result.append(
            {
                "time": _format_time(base_time + timedelta(seconds=seconds)),
                "value": bucket["value_sum"] / count,
            }
        )
    return result
