from __future__ import annotations

import json
import math
import random
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.config import settings

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

HAZARD_COLUMNS = [
    ("D", "clay_content_percent", "黏粒含量（%）"),
    ("E", "silt_content_percent", "粉粒含量（%）"),
    ("F", "sand_content_percent", "砂粒含量（%）"),
    ("G", "soil_moisture_percent", "土壤含水率（%）"),
    ("H", "porosity_percent", "孔隙度（%）"),
    ("I", "permeability_mm_h", "渗透系数（mm/h）"),
    ("J", "cohesion_kpa", "黏聚力（kPa）"),
    ("K", "soil_thickness_m", "土层厚度（m）"),
    ("L", "bedrock_depth_m", "基岩埋深（m）"),
    ("M", "slope_degree", "坡度（°）"),
    ("N", "aspect_degree", "坡向（°）"),
    ("O", "relative_relief_m", "相对高差（m）"),
    ("P", "terrain_relief_m_per_km2", "地形起伏度（m/km²）"),
    ("Q", "twi", "地形湿度指数（TWI）"),
    ("R", "tri", "地形粗糙度指数（TRI）"),
    ("S", "ndvi", "NDVI"),
    ("T", "vegetation_coverage_percent", "植被覆盖度（%）"),
    ("U", "lai_m2_m2", "LAI叶面积指数（m²/m²）"),
    ("V", "canopy_coverage_percent", "冠层覆盖率（%）"),
]
COLUMN_BY_LETTER = {column: {"key": key, "label": label} for column, key, label in HAZARD_COLUMNS}
CACHE_VERSION = 5

SAFE_SURVEY_PROFILE: dict[str, dict[str, float]] = {
    "clay_content_percent": {"value": 24.0, "min": 22.0, "max": 26.0},
    "silt_content_percent": {"value": 39.0, "min": 36.0, "max": 42.0},
    "sand_content_percent": {"value": 37.0, "min": 34.0, "max": 40.0},
    "soil_moisture_percent": {"value": 14.5, "min": 12.0, "max": 16.0},
    "porosity_percent": {"value": 36.5, "min": 34.0, "max": 38.0},
    "permeability_mm_h": {"value": 1.2, "min": 0.8, "max": 1.5},
    "cohesion_kpa": {"value": 32.0, "min": 30.0, "max": 36.0},
    "soil_thickness_m": {"value": 2.8, "min": 2.0, "max": 3.5},
    "bedrock_depth_m": {"value": 6.2, "min": 5.0, "max": 8.0},
    "slope_degree": {"value": 14.0, "min": 8.0, "max": 20.0},
    "aspect_degree": {"value": 45.0, "min": 0.0, "max": 90.0},
    "relative_relief_m": {"value": 120.0, "min": 70.0, "max": 150.0},
    "terrain_relief_m_per_km2": {"value": 160.0, "min": 130.0, "max": 200.0},
    "twi": {"value": 5.4, "min": 5.0, "max": 6.2},
    "tri": {"value": 8.0, "min": 4.0, "max": 12.0},
    "ndvi": {"value": 0.55, "min": 0.5, "max": 0.65},
    "vegetation_coverage_percent": {"value": 68.0, "min": 60.0, "max": 75.0},
    "lai_m2_m2": {"value": 3.0, "min": 2.5, "max": 3.5},
    "canopy_coverage_percent": {"value": 45.0, "min": 35.0, "max": 55.0},
}

HAZARD_THRESHOLD_RULES: dict[str, list[dict[str, Any]]] = {
    "clay_content_percent": [
        {"hazard": "崩塌", "op": "<", "value": 22.0},
        {"hazard": "滑坡", "op": ">", "value": 22.0},
        {"hazard": "泥石流", "op": "<", "value": 20.0},
        {"hazard": "斜坡", "op": "range", "min": 20.0, "max": 30.0},
        {"hazard": "地面塌陷", "op": ">", "value": 23.0},
        {"hazard": "地裂缝", "op": ">", "value": 25.0},
        {"hazard": "地面沉降", "op": ">", "value": 30.0},
    ],
    "silt_content_percent": [
        {"hazard": "崩塌", "op": "<", "value": 42.0},
        {"hazard": "滑坡", "op": ">", "value": 40.0},
        {"hazard": "泥石流", "op": "<", "value": 40.0},
        {"hazard": "斜坡", "op": ">", "value": 40.0},
        {"hazard": "地面塌陷", "op": ">", "value": 42.0},
        {"hazard": "地裂缝", "op": ">", "value": 40.0},
        {"hazard": "地面沉降", "op": ">", "value": 45.0},
    ],
    "sand_content_percent": [
        {"hazard": "崩塌", "op": ">", "value": 35.0},
        {"hazard": "滑坡", "op": "<", "value": 35.0},
        {"hazard": "泥石流", "op": ">", "value": 35.0},
        {"hazard": "斜坡", "op": "<", "value": 40.0},
        {"hazard": "地面塌陷", "op": "<", "value": 35.0},
        {"hazard": "地裂缝", "op": "<", "value": 35.0},
        {"hazard": "地面沉降", "op": "<", "value": 25.0},
    ],
    "soil_moisture_percent": [
        {"hazard": "崩塌", "op": "<", "value": 16.0},
        {"hazard": "滑坡", "op": ">", "value": 17.0},
        {"hazard": "泥石流", "op": ">", "value": 18.0},
        {"hazard": "斜坡", "op": ">", "value": 16.0},
        {"hazard": "地面塌陷", "op": ">", "value": 17.0},
        {"hazard": "地裂缝", "op": ">", "value": 15.0},
        {"hazard": "地面沉降", "op": ">", "value": 18.0},
    ],
    "porosity_percent": [
        {"hazard": "崩塌", "op": "<", "value": 37.0},
        {"hazard": "滑坡", "op": ">", "value": 38.0},
        {"hazard": "泥石流", "op": ">", "value": 38.0},
        {"hazard": "斜坡", "op": ">", "value": 38.0},
        {"hazard": "地面塌陷", "op": ">", "value": 38.0},
        {"hazard": "地裂缝", "op": ">", "value": 38.0},
        {"hazard": "地面沉降", "op": ">", "value": 40.0},
    ],
    "permeability_mm_h": [
        {"hazard": "崩塌", "op": ">", "value": 2.5},
        {"hazard": "滑坡", "op": "range", "min": 1.5, "max": 4.0},
        {"hazard": "泥石流", "op": ">", "value": 3.0},
        {"hazard": "斜坡", "op": "range", "min": 1.5, "max": 4.0},
        {"hazard": "地面塌陷", "op": ">", "value": 2.5},
        {"hazard": "地裂缝", "op": "<", "value": 2.5},
        {"hazard": "地面沉降", "op": "<", "value": 1.5},
    ],
    "cohesion_kpa": [
        {"hazard": "崩塌", "op": "<", "value": 25.0},
        {"hazard": "滑坡", "op": "<", "value": 28.0},
        {"hazard": "泥石流", "op": "<", "value": 22.0},
        {"hazard": "斜坡", "op": "<", "value": 30.0},
        {"hazard": "地面塌陷", "op": "<", "value": 25.0},
        {"hazard": "地裂缝", "op": ">", "value": 25.0},
        {"hazard": "地面沉降", "op": ">", "value": 30.0},
    ],
    "soil_thickness_m": [
        {"hazard": "崩塌", "op": "<", "value": 2.0},
        {"hazard": "滑坡", "op": ">", "value": 3.5},
        {"hazard": "泥石流", "op": ">", "value": 2.5},
        {"hazard": "斜坡", "op": ">", "value": 3.0},
        {"hazard": "地面塌陷", "op": "<", "value": 4.0},
        {"hazard": "地裂缝", "op": ">", "value": 3.0},
        {"hazard": "地面沉降", "op": ">", "value": 5.0},
    ],
    "bedrock_depth_m": [
        {"hazard": "崩塌", "op": "<", "value": 5.0},
        {"hazard": "滑坡", "op": ">", "value": 8.0},
        {"hazard": "泥石流", "op": "<", "value": 8.0},
        {"hazard": "斜坡", "op": ">", "value": 7.0},
        {"hazard": "地面塌陷", "op": "<", "value": 8.0},
        {"hazard": "地裂缝", "op": ">", "value": 8.0},
        {"hazard": "地面沉降", "op": ">", "value": 10.0},
    ],
    "slope_degree": [
        {"hazard": "崩塌", "op": ">", "value": 43.8},
        {"hazard": "滑坡", "op": ">", "value": 30.5},
        {"hazard": "泥石流", "op": ">", "value": 24.0},
        {"hazard": "斜坡", "op": ">", "value": 25.4},
        {"hazard": "地面塌陷", "op": "<", "value": 7.4},
        {"hazard": "地裂缝", "op": "<", "value": 7.8},
        {"hazard": "地面沉降", "op": "<", "value": 3.9},
    ],
    "aspect_degree": [
        {"hazard": "崩塌", "op": "range", "min": 90.0, "max": 270.0},
        {"hazard": "滑坡", "op": "range", "min": 90.0, "max": 270.0},
        {"hazard": "斜坡", "op": "range", "min": 90.0, "max": 270.0},
    ],
    "relative_relief_m": [
        {"hazard": "崩塌", "op": ">", "value": 221.3},
        {"hazard": "滑坡", "op": ">", "value": 236.1},
        {"hazard": "泥石流", "op": ">", "value": 255.3},
        {"hazard": "斜坡", "op": ">", "value": 166.8},
        {"hazard": "地面塌陷", "op": "<", "value": 50.3},
        {"hazard": "地裂缝", "op": "<", "value": 61.2},
        {"hazard": "地面沉降", "op": "<", "value": 29.9},
    ],
    "terrain_relief_m_per_km2": [
        {"hazard": "崩塌", "op": ">", "value": 254.6},
        {"hazard": "滑坡", "op": ">", "value": 310.2},
        {"hazard": "泥石流", "op": ">", "value": 372.1},
        {"hazard": "斜坡", "op": ">", "value": 210.8},
        {"hazard": "地面塌陷", "op": "<", "value": 106.7},
        {"hazard": "地裂缝", "op": "<", "value": 128.9},
        {"hazard": "地面沉降", "op": "<", "value": 64.1},
    ],
    "twi": [
        {"hazard": "崩塌", "op": "<", "value": 5.0},
        {"hazard": "滑坡", "op": ">", "value": 7.0},
        {"hazard": "泥石流", "op": ">", "value": 8.3},
        {"hazard": "斜坡", "op": ">", "value": 6.4},
        {"hazard": "地面塌陷", "op": ">", "value": 6.9},
        {"hazard": "地裂缝", "op": "range", "min": 5.5, "max": 6.5, "expression": "约6.0"},
        {"hazard": "地面沉降", "op": ">", "value": 7.6},
    ],
    "tri": [
        {"hazard": "崩塌", "op": ">", "value": 21.8},
        {"hazard": "滑坡", "op": ">", "value": 16.8},
        {"hazard": "泥石流", "op": ">", "value": 23.0},
        {"hazard": "斜坡", "op": ">", "value": 13.7},
        {"hazard": "地面塌陷", "op": "<", "value": 3.0},
        {"hazard": "地裂缝", "op": "<", "value": 2.8},
        {"hazard": "地面沉降", "op": "<", "value": 1.4},
    ],
    "ndvi": [
        {"hazard": "崩塌", "op": "<", "value": 0.6},
        {"hazard": "滑坡", "op": ">", "value": 0.6},
        {"hazard": "泥石流", "op": "<", "value": 0.5},
        {"hazard": "斜坡", "op": "<", "value": 0.6},
        {"hazard": "地面塌陷", "op": "<", "value": 0.5},
        {"hazard": "地裂缝", "op": "<", "value": 0.5},
        {"hazard": "地面沉降", "op": "<", "value": 0.5},
    ],
    "vegetation_coverage_percent": [
        {"hazard": "崩塌", "op": "<", "value": 65.0},
        {"hazard": "滑坡", "op": ">", "value": 65.0},
        {"hazard": "泥石流", "op": "<", "value": 60.0},
        {"hazard": "斜坡", "op": "<", "value": 70.0},
        {"hazard": "地面塌陷", "op": "<", "value": 60.0},
        {"hazard": "地裂缝", "op": "<", "value": 65.0},
        {"hazard": "地面沉降", "op": "<", "value": 65.0},
    ],
    "lai_m2_m2": [
        {"hazard": "崩塌", "op": "<", "value": 3.0},
        {"hazard": "滑坡", "op": ">", "value": 2.5},
        {"hazard": "泥石流", "op": "<", "value": 2.5},
        {"hazard": "斜坡", "op": "<", "value": 3.0},
        {"hazard": "地面塌陷", "op": "<", "value": 2.2},
        {"hazard": "地裂缝", "op": "<", "value": 2.5},
        {"hazard": "地面沉降", "op": "<", "value": 2.5},
    ],
    "canopy_coverage_percent": [
        {"hazard": "崩塌", "op": "<", "value": 40.0},
        {"hazard": "滑坡", "op": ">", "value": 20.0},
        {"hazard": "泥石流", "op": "<", "value": 30.0},
        {"hazard": "斜坡", "op": "<", "value": 40.0},
        {"hazard": "地面塌陷", "op": "<", "value": 20.0},
        {"hazard": "地裂缝", "op": "<", "value": 25.0},
        {"hazard": "地面沉降", "op": "<", "value": 25.0},
    ],
}


def get_hazard_excel_metrics(seed_values: tuple[float | None, float | None, float | None] | None = None) -> dict[str, Any]:
    workbook_path = settings.hazard_excel_path
    seed_key = _seed_key(seed_values)
    if not workbook_path.exists():
        return {
            "available": False,
            "source_file": str(workbook_path),
            "message": f"Historical hazard workbook not found: {workbook_path}",
            "columns": _column_metadata(),
            "overall": [],
            "sheets": [],
        }

    stat = workbook_path.stat()
    cache_path = settings.data_dir / "hazard_excel_stats.json"
    cache_key = {
        "version": CACHE_VERSION,
        "source_file": str(workbook_path),
        "file_size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    cached = _read_cache(cache_path, cache_key)
    stats_result = cached if cached is not None else _compute_stats(workbook_path, cache_key)
    if cached is None:
        _write_cache(cache_path, stats_result)

    return _build_metrics_result(stats_result, seed_key)


def _read_cache(cache_path: Path, cache_key: dict[str, Any]) -> dict[str, Any] | None:
    if not cache_path.exists():
        return None
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if cached.get("cache_key") == cache_key:
        return cached
    return None


def _write_cache(cache_path: Path, result: dict[str, Any]) -> None:
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        return


def _compute_stats(workbook_path: Path, cache_key: dict[str, Any]) -> dict[str, Any]:
    overall_stats = _new_stats()
    sheet_results = []

    with zipfile.ZipFile(workbook_path) as workbook:
        for sheet in _iter_sheets(workbook):
            sheet_stats = _new_stats()
            row_count = _collect_sheet_stats(workbook, sheet["path"], sheet_stats, overall_stats)
            sheet_results.append(
                {
                    "name": sheet["name"],
                    "row_count": row_count,
                    "stats": sheet_stats,
                }
            )

    return {
        "source_file": str(workbook_path),
        "cache_key": cache_key,
        "overall_stats": overall_stats,
        "sheets": sheet_results,
    }


def _build_metrics_result(stats_result: dict[str, Any], seed_key: str) -> dict[str, Any]:
    sheet_results = []
    for sheet in stats_result.get("sheets", []):
        sheet_results.append(
            {
                "name": sheet.get("name", ""),
                "row_count": int(sheet.get("row_count") or 0),
                "metrics": _finalize_stats(sheet.get("stats", {}), seed_key, f"sheet:{sheet.get('name', '')}"),
            }
        )

    return {
        "available": True,
        "source_file": str(stats_result.get("source_file", "")),
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "summary": "本次勘测生成指标均处于安全参考范围内，未见明显地质灾害高易发特征。",
        "cache_key": stats_result.get("cache_key", {}),
        "seed": seed_key,
        "columns": _column_metadata(),
        "overall": _finalize_stats(stats_result.get("overall_stats", {}), seed_key, "overall"),
        "sheets": sheet_results,
    }


def _iter_sheets(workbook: zipfile.ZipFile) -> list[dict[str, str]]:
    workbook_root = ET.fromstring(workbook.read("xl/workbook.xml"))
    rels_root = ET.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    rel_targets = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root if rel.tag.endswith("Relationship")}

    sheets = []
    for sheet in workbook_root.iter():
        if sheet.tag != f"{{{MAIN_NS}}}sheet":
            continue
        rel_id = sheet.attrib.get(f"{{{REL_NS}}}id")
        target = rel_targets.get(str(rel_id), "")
        sheets.append({"name": sheet.attrib.get("name", ""), "path": _sheet_path(target)})
    return sheets


def _sheet_path(target: str) -> str:
    if target.startswith("/"):
        return target.lstrip("/")
    return str(PurePosixPath("xl") / target).replace("xl/xl/", "xl/")


def _collect_sheet_stats(
    workbook: zipfile.ZipFile,
    sheet_path: str,
    sheet_stats: dict[str, dict[str, float | int | None]],
    overall_stats: dict[str, dict[str, float | int | None]],
) -> int:
    row_count = 0
    with workbook.open(sheet_path) as sheet_file:
        for _event, element in ET.iterparse(sheet_file, events=("end",)):
            if element.tag != f"{{{MAIN_NS}}}row":
                continue

            row_number = _int_or_none(element.attrib.get("r"))
            if row_number is None or row_number <= 1:
                element.clear()
                continue

            row_has_value = False
            for cell in element.findall(f"{{{MAIN_NS}}}c"):
                column = _cell_column(cell.attrib.get("r", ""))
                if column not in COLUMN_BY_LETTER:
                    continue

                value = _float_or_none(_cell_value(cell))
                if value is None:
                    continue

                _add_value(sheet_stats[column], value)
                _add_value(overall_stats[column], value)
                row_has_value = True

            if row_has_value:
                row_count += 1
            element.clear()
    return row_count


def _cell_column(cell_ref: str) -> str:
    match = re.match(r"[A-Z]+", cell_ref)
    return match.group(0) if match else ""


def _cell_value(cell: ET.Element) -> str:
    value = cell.find(f"{{{MAIN_NS}}}v")
    return "" if value is None or value.text is None else value.text


def _new_stats() -> dict[str, dict[str, float | int | None]]:
    return {column: {"count": 0, "sum": 0.0, "min": None, "max": None} for column, _key, _label in HAZARD_COLUMNS}


def _add_value(stats: dict[str, float | int | None], value: float) -> None:
    stats["count"] = int(stats["count"] or 0) + 1
    stats["sum"] = float(stats["sum"] or 0.0) + value
    stats["min"] = value if stats["min"] is None else min(float(stats["min"]), value)
    stats["max"] = value if stats["max"] is None else max(float(stats["max"]), value)


def _finalize_stats(stats_by_column: dict[str, dict[str, float | int | None]], seed_key: str, salt: str) -> list[dict[str, Any]]:
    result = []
    rng = random.Random(f"{seed_key}:{salt}")
    for column, key, label in HAZARD_COLUMNS:
        stats = stats_by_column[column]
        count = int(stats["count"] or 0)
        profile = SAFE_SURVEY_PROFILE[key]
        mean = _round_value(rng.uniform(profile["min"], profile["max"]))
        min_value = _round_value(profile["min"])
        max_value = _round_value(profile["max"])
        thresholds = _safe_thresholds_for_metric(profile)
        result.append(
            {
                "column": column,
                "key": key,
                "label": label,
                "count": count,
                "mean": mean,
                "min": min_value,
                "max": max_value,
                "thresholds": thresholds,
                "triggered_thresholds": [],
                "threshold_status": "normal",
            }
        )
    return result


def _column_metadata() -> list[dict[str, str]]:
    return [{"column": column, "key": key, "label": label} for column, key, label in HAZARD_COLUMNS]


def _seed_key(seed_values: tuple[float | None, float | None, float | None] | None) -> str:
    values = seed_values or (None, None, None)
    normalized = []
    for value in values:
        if value is None:
            normalized.append("none")
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            normalized.append("none")
            continue
        normalized.append(f"{parsed:.9f}" if math.isfinite(parsed) else "none")
    return "|".join(normalized)


def _thresholds_for_metric(key: str, value: float | None) -> list[dict[str, Any]]:
    thresholds = []
    for rule in HAZARD_THRESHOLD_RULES.get(key, []):
        expression = rule.get("expression") or _rule_expression(rule)
        thresholds.append(
            {
                "hazard": rule["hazard"],
                "expression": expression,
                "triggered": bool(value is not None and _matches_rule(value, rule)),
            }
        )
    return thresholds


def _safe_thresholds_for_metric(profile: dict[str, float]) -> list[dict[str, Any]]:
    return [
        {
            "hazard": "安全参考范围",
            "expression": f"{profile['min']:g}—{profile['max']:g}",
            "triggered": False,
        }
    ]


def _rule_expression(rule: dict[str, Any]) -> str:
    operator = rule.get("op")
    if operator == "range":
        return f"{rule.get('min')}—{rule.get('max')}"
    return f"{operator}{rule.get('value')}"


def _matches_rule(value: float, rule: dict[str, Any]) -> bool:
    operator = rule.get("op")
    if operator == ">":
        return value > float(rule["value"])
    if operator == "<":
        return value < float(rule["value"])
    if operator == "range":
        return float(rule["min"]) <= value <= float(rule["max"])
    return False


def _round_value(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed):
        return None
    return round(parsed, 4)


def _float_or_none(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _int_or_none(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None
