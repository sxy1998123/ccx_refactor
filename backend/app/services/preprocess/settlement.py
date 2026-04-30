from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import numpy as np


IMU_PATTERN = re.compile(
    r"Time:(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d+),"
    r"accel:([-\d\.]+),([-\d\.]+),([-\d\.]+),"
    r"gyro:([-\d\.]+),([-\d\.]+),([-\d\.]+),"
    r"euler:([-\d\.]+),([-\d\.]+),([-\d\.]+),"
    r"quat:([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+)"
)
RMC_PATTERN = re.compile(r"Time:(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}\.\d+)\$GNRMC")
GGA_PATTERN = re.compile(r"^\$G[NP]GGA,.*")


def _nmea_to_decimal(coord_text: str, hemi: str) -> float:
    value = float(coord_text)
    degree = int(value / 100)
    minute = value - degree * 100
    decimal = degree + minute / 60.0
    return -decimal if hemi in {"S", "W"} else decimal


def _parse_gga(line: str) -> dict | None:
    parts = line.strip().split(",")
    if len(parts) < 10:
        return None

    fix_quality = parts[6].strip()
    if fix_quality in {"", "0"}:
        return None

    lat_text = parts[2].strip()
    lat_hemi = parts[3].strip()
    lon_text = parts[4].strip()
    lon_hemi = parts[5].strip()
    alt_text = parts[9].strip()
    if not lat_text or not lon_text or not alt_text:
        return None

    sat_num = parts[7].strip()
    hdop = parts[8].strip()
    return {
        "lat": _nmea_to_decimal(lat_text, lat_hemi),
        "lon": _nmea_to_decimal(lon_text, lon_hemi),
        "alt": float(alt_text),
        "sat_num": int(sat_num) if sat_num else None,
        "hdop": float(hdop) if hdop else None,
        "fix_quality": int(fix_quality),
    }


def _detect_target_date(file_path: Path) -> str | None:
    with file_path.open("r", encoding="utf-8", errors="ignore") as file:
        for raw_line in file:
            line = raw_line.strip()
            imu_match = IMU_PATTERN.match(line)
            if imu_match and not imu_match.group(1).startswith("2000-00-00"):
                return imu_match.group(1)

            rmc_match = RMC_PATTERN.match(line)
            if rmc_match and not rmc_match.group(1).startswith("2000-00-00"):
                return rmc_match.group(1)

    return None


def process_tower_txt(file_path: str | Path) -> dict:
    source_path = Path(file_path)
    target_date = _detect_target_date(source_path)
    if target_date is None:
        raise ValueError(f"No valid target date found in {source_path}")

    gnss_records = []
    imu_records = []
    current_rmc_date = None

    with source_path.open("r", encoding="utf-8", errors="ignore") as file:
        for raw_line in file:
            line = raw_line.strip()
            rmc_match = RMC_PATTERN.match(line)
            if rmc_match:
                date_text = rmc_match.group(1)
                current_rmc_date = date_text if date_text == target_date else None
                continue

            if GGA_PATTERN.match(line):
                if current_rmc_date != target_date:
                    continue
                gga = _parse_gga(line)
                if gga is not None:
                    gnss_records.append(gga)
                continue

            imu_match = IMU_PATTERN.match(line)
            if not imu_match or imu_match.group(1) != target_date:
                continue

            try:
                timestamp = datetime.strptime(
                    f"{imu_match.group(1)} {imu_match.group(2)}",
                    "%Y-%m-%d %H:%M:%S.%f",
                )
                acceleration = np.array(
                    [float(imu_match.group(3)), float(imu_match.group(4)), float(imu_match.group(5))],
                    dtype=float,
                )
            except ValueError:
                continue

            imu_records.append({"t": timestamp, "acc": acceleration})

    gnss = _summarize_gnss(gnss_records)
    imu = _summarize_imu(imu_records)
    return {
        "source_file": str(source_path),
        "file_name": source_path.name,
        "target_date": target_date,
        "gnss": gnss,
        "imu": imu,
    }


def _summarize_gnss(records: list[dict]) -> dict:
    if not records:
        return {
            "valid_count": 0,
            "mean_lat": None,
            "mean_lon": None,
            "mean_alt_m": None,
        }

    lat_values = np.array([record["lat"] for record in records], dtype=float)
    lon_values = np.array([record["lon"] for record in records], dtype=float)
    alt_values = np.array([record["alt"] for record in records], dtype=float)
    return {
        "valid_count": len(records),
        "mean_lat": float(np.mean(lat_values)),
        "mean_lon": float(np.mean(lon_values)),
        "mean_alt_m": float(np.mean(alt_values)),
    }


def _summarize_imu(records: list[dict]) -> dict:
    if len(records) < 2:
        return {
            "valid_data_count": len(records),
            "duration_minutes": 0.0,
            "x_drift_mm": None,
            "y_drift_mm": None,
            "z_drift_mm": None,
            "total_drift_mm": None,
        }

    records.sort(key=lambda item: item["t"])
    sample_rate = 100.0
    delta_time = 1.0 / sample_rate

    start_time = records[0]["t"]
    static_samples = [item["acc"] for item in records if (item["t"] - start_time).total_seconds() <= 5.0]
    if not static_samples:
        static_samples = [records[0]["acc"]]

    current_bias = np.mean(np.array(static_samples, dtype=float), axis=0)
    velocity = np.zeros(3, dtype=float)
    position = np.zeros(3, dtype=float)

    bias_alpha = 0.999
    velocity_leak = 0.995
    position_leak = 0.999
    valid_data_count = 0

    for item in records[1:]:
        current_bias = bias_alpha * current_bias + (1.0 - bias_alpha) * item["acc"]
        residual_acc = item["acc"] - current_bias
        velocity = (velocity + residual_acc * delta_time) * velocity_leak
        position = (position + velocity * delta_time) * position_leak
        valid_data_count += 1

    position = position * 0.01
    total_drift_m = float(np.linalg.norm(position))
    return {
        "valid_data_count": valid_data_count,
        "duration_minutes": valid_data_count / sample_rate / 60,
        "x_drift_m": float(position[0]),
        "y_drift_m": float(position[1]),
        "z_drift_m": float(position[2]),
        "total_drift_m": total_drift_m,
        "x_drift_mm": float(position[0] * 1000),
        "y_drift_mm": float(position[1] * 1000),
        "z_drift_mm": float(position[2] * 1000),
        "total_drift_mm": total_drift_m * 1000,
    }
