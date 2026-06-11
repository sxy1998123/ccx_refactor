from __future__ import annotations

import math
from functools import lru_cache
from pathlib import Path
from typing import Any


def extract_structural_metrics_from_h5(h5_path: str | Path | None) -> dict[str, Any]:
    if not h5_path:
        return _empty_metrics("h5 path is empty")

    path = Path(h5_path)
    if not path.exists():
        return _empty_metrics(f"h5 file not found: {path}")

    return _extract_structural_metrics_cached(str(path.resolve()))


@lru_cache(maxsize=256)
def _extract_structural_metrics_cached(h5_path: str) -> dict[str, Any]:
    try:
        import h5py
        import numpy as np
    except ImportError as error:
        return _empty_metrics(f"h5py/numpy is required: {error}")

    metrics = _empty_metrics("")
    try:
        with h5py.File(h5_path, "r") as h5:
            part_name = _find_mesh_part_name(h5)
            if not part_name:
                return _empty_metrics("mesh part not found")

            coordinates = _read_node_coordinates(h5, part_name, np)
            metrics.update(_compute_tower_tilt(h5, part_name, coordinates, np))
            metrics.update(_compute_max_strain(h5, part_name, np))
    except Exception as error:  # noqa: BLE001 - metrics should not fail the risk result.
        return _empty_metrics(str(error))

    errors = [value for key, value in metrics.items() if key.endswith("_error") and value]
    metrics["structural_metrics_error"] = "; ".join(errors)
    return metrics


def _empty_metrics(error: str) -> dict[str, Any]:
    return {
        "tower_tilt_deg": None,
        "tower_tilt_x_deg": None,
        "tower_tilt_y_deg": None,
        "tower_tilt_node_count": None,
        "tower_tilt_error": error,
        "max_abs_strain": None,
        "max_abs_strain_micro": None,
        "max_strain_component": None,
        "max_strain_location": "",
        "strain_error": error,
        "structural_metrics_error": error,
    }


def _find_mesh_part_name(h5: Any) -> str:
    if "/Parts" not in h5:
        return ""

    best_part = ""
    best_node_count = -1
    for part_name in h5["/Parts"]:
        part_path = f"/Parts/{part_name}"
        coordinates_path = f"{part_path}/Nodes/Coordinates"
        if coordinates_path not in h5:
            continue
        node_count = int(getattr(h5[coordinates_path], "shape", [0])[0])
        if node_count > best_node_count:
            best_node_count = node_count
            best_part = str(part_name)
    return best_part


def _read_node_coordinates(h5: Any, part_name: str, np: Any) -> Any:
    coordinates_path = f"/Parts/{part_name}/Nodes/Coordinates"
    if coordinates_path not in h5:
        raise ValueError(f"node coordinates not found: {coordinates_path}")

    coordinates = np.asarray(h5[coordinates_path][:], dtype=float)
    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise ValueError(f"unexpected coordinate shape: {coordinates.shape}")
    return coordinates


def _compute_tower_tilt(h5: Any, part_name: str, coordinates: Any, np: Any) -> dict[str, Any]:
    real_path = _find_step_field_real_path(h5, part_name, "U")
    if not real_path:
        return {
            "tower_tilt_deg": None,
            "tower_tilt_x_deg": None,
            "tower_tilt_y_deg": None,
            "tower_tilt_node_count": None,
            "tower_tilt_error": "U displacement dataset not found",
        }

    displacement = np.asarray(h5[real_path][:], dtype=float)
    if displacement.ndim != 2 or displacement.shape[0] != coordinates.shape[0] or displacement.shape[1] < 3:
        return {
            "tower_tilt_deg": None,
            "tower_tilt_x_deg": None,
            "tower_tilt_y_deg": None,
            "tower_tilt_node_count": None,
            "tower_tilt_error": f"unexpected U shape: {displacement.shape}",
        }

    z_values = coordinates[:, 2]
    z_min = float(np.min(z_values))
    z_max = float(np.max(z_values))
    height = z_max - z_min
    if height <= 0:
        return {
            "tower_tilt_deg": None,
            "tower_tilt_x_deg": None,
            "tower_tilt_y_deg": None,
            "tower_tilt_node_count": None,
            "tower_tilt_error": "tower height is zero",
        }

    bottom_mask, top_mask = _select_end_node_masks(z_values, height, np)
    bottom_count = int(np.count_nonzero(bottom_mask))
    top_count = int(np.count_nonzero(top_mask))
    if bottom_count == 0 or top_count == 0:
        return {
            "tower_tilt_deg": None,
            "tower_tilt_x_deg": None,
            "tower_tilt_y_deg": None,
            "tower_tilt_node_count": None,
            "tower_tilt_error": "top or bottom node group is empty",
        }

    bottom_origin = np.mean(coordinates[bottom_mask, :3], axis=0)
    top_origin = np.mean(coordinates[top_mask, :3], axis=0)
    bottom_deformed = np.mean(coordinates[bottom_mask, :3] + displacement[bottom_mask, :3], axis=0)
    top_deformed = np.mean(coordinates[top_mask, :3] + displacement[top_mask, :3], axis=0)

    original_axis = top_origin - bottom_origin
    deformed_axis = top_deformed - bottom_deformed
    original_norm = float(np.linalg.norm(original_axis))
    deformed_norm = float(np.linalg.norm(deformed_axis))
    if original_norm <= 0 or deformed_norm <= 0:
        return {
            "tower_tilt_deg": None,
            "tower_tilt_x_deg": None,
            "tower_tilt_y_deg": None,
            "tower_tilt_node_count": None,
            "tower_tilt_error": "tower axis length is zero",
        }

    cosine = float(np.dot(original_axis, deformed_axis) / (original_norm * deformed_norm))
    angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine))))

    relative_displacement = np.mean(displacement[top_mask, :3], axis=0) - np.mean(displacement[bottom_mask, :3], axis=0)
    vertical_span = abs(float(original_axis[2])) or height
    tilt_x = math.degrees(math.atan2(float(relative_displacement[0]), vertical_span))
    tilt_y = math.degrees(math.atan2(float(relative_displacement[1]), vertical_span))

    return {
        "tower_tilt_deg": float(angle),
        "tower_tilt_x_deg": float(tilt_x),
        "tower_tilt_y_deg": float(tilt_y),
        "tower_tilt_node_count": {"top": top_count, "bottom": bottom_count},
        "tower_tilt_error": "",
    }


def _select_end_node_masks(z_values: Any, height: float, np: Any) -> tuple[Any, Any]:
    z_min = float(np.min(z_values))
    z_max = float(np.max(z_values))
    band = height * 0.05
    bottom_mask = z_values <= z_min + band
    top_mask = z_values >= z_max - band

    minimum_count = max(3, int(math.ceil(len(z_values) * 0.02)))
    if int(np.count_nonzero(bottom_mask)) >= minimum_count and int(np.count_nonzero(top_mask)) >= minimum_count:
        return bottom_mask, top_mask

    order = np.argsort(z_values)
    count = min(len(z_values), minimum_count)
    bottom_mask = np.zeros(len(z_values), dtype=bool)
    top_mask = np.zeros(len(z_values), dtype=bool)
    bottom_mask[order[:count]] = True
    top_mask[order[-count:]] = True
    return bottom_mask, top_mask


def _compute_max_strain(h5: Any, part_name: str, np: Any) -> dict[str, Any]:
    base_path = _find_element_field_class_path(h5, part_name, "E")
    if not base_path:
        return {
            "max_abs_strain": None,
            "max_abs_strain_micro": None,
            "max_strain_component": None,
            "max_strain_location": "",
            "strain_error": "E strain dataset not found",
        }

    max_abs_strain: float | None = None
    max_component: int | None = None
    max_location = ""
    for location_name in h5[base_path]:
        real_path = f"{base_path}/{location_name}/Real"
        if real_path not in h5:
            continue
        real = np.asarray(h5[real_path][:], dtype=float)
        if real.size == 0:
            continue
        scores = np.abs(real)
        scores = np.where(np.isfinite(scores), scores, -np.inf)
        if not np.isfinite(scores).any():
            continue
        flat_index = int(np.argmax(scores))
        value = float(scores.flat[flat_index])
        if max_abs_strain is not None and value <= max_abs_strain:
            continue
        index = np.unravel_index(flat_index, real.shape)
        max_abs_strain = value
        max_component = int(index[1] + 1) if len(index) > 1 else 1
        max_location = str(location_name)

    if max_abs_strain is None:
        return {
            "max_abs_strain": None,
            "max_abs_strain_micro": None,
            "max_strain_component": None,
            "max_strain_location": "",
            "strain_error": "E strain dataset is empty",
        }

    return {
        "max_abs_strain": max_abs_strain,
        "max_abs_strain_micro": max_abs_strain * 1_000_000.0,
        "max_strain_component": max_component,
        "max_strain_location": max_location,
        "strain_error": "",
    }


def _find_step_field_real_path(h5: Any, part_name: str, field_name: str) -> str:
    steps_path = "/Steps"
    if steps_path not in h5:
        return ""

    candidates: list[str] = []

    def visitor(name: str, obj: Any) -> None:
        path = f"{steps_path}/{name}"
        if not hasattr(obj, "shape") or not path.endswith("/Real"):
            return
        if f"/{field_name}/" not in path:
            return
        if f"/{part_name}-" in path or f"/{part_name}/" in path:
            candidates.append(path)

    h5[steps_path].visititems(visitor)
    if candidates:
        return candidates[0]

    fallback_candidates: list[str] = []

    def fallback_visitor(name: str, obj: Any) -> None:
        path = f"{steps_path}/{name}"
        if hasattr(obj, "shape") and f"/{field_name}/" in path and path.endswith("/Real"):
            fallback_candidates.append(path)

    h5[steps_path].visititems(fallback_visitor)
    return fallback_candidates[0] if fallback_candidates else ""


def _find_element_field_class_path(h5: Any, part_name: str, field_name: str) -> str:
    steps_path = "/Steps"
    if steps_path not in h5:
        return ""

    candidates: list[str] = []

    def visitor(name: str, obj: Any) -> None:
        path = f"{steps_path}/{name}"
        if f"/{field_name}/" not in path or not path.endswith("ElementClass:0"):
            return
        if f"/{part_name}-" in path or f"/{part_name}/" in path:
            candidates.append(path)

    h5[steps_path].visititems(visitor)
    if candidates:
        return candidates[0]

    fallback_candidates: list[str] = []

    def fallback_visitor(name: str, obj: Any) -> None:
        path = f"{steps_path}/{name}"
        if f"/{field_name}/" in path and path.endswith("ElementClass:0"):
            fallback_candidates.append(path)

    h5[steps_path].visititems(fallback_visitor)
    return fallback_candidates[0] if fallback_candidates else ""
