from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


class StressCloudError(RuntimeError):
    pass


@lru_cache(maxsize=8)
def get_stress_cloud_for_h5(h5_path: Path) -> dict[str, Any]:
    return get_field_cloud_for_h5(h5_path, "stress", "magnitude")


@lru_cache(maxsize=32)
def get_field_cloud_for_h5(h5_path: Path, field: str = "stress", axis: str = "magnitude") -> dict[str, Any]:
    h5_path = Path(h5_path)
    if not h5_path.exists():
        raise StressCloudError(f"result h5 not found: {h5_path}")

    try:
        import h5py
        import numpy as np
    except ImportError as error:
        raise StressCloudError(f"h5py/numpy is required to parse result h5: {error}") from error

    stress_unit = _detect_stress_unit(h5_path)
    stress_factor = _stress_unit_to_pa_factor(stress_unit)
    displacement_unit = _detect_length_unit(h5_path)
    displacement_factor = _length_unit_to_m_factor(displacement_unit)
    field_name, axis_name = _normalize_field_axis(field, axis)

    try:
        with h5py.File(h5_path, "r") as h5:
            part_name = _find_mesh_part_name(h5)
            if not part_name:
                raise StressCloudError(f"result h5 has no supported mesh part under /Parts: {h5_path}")

            part_path = f"/Parts/{part_name}"
            nodes_path = f"{part_path}/Nodes/Coordinates"
            node_labels_path = f"{part_path}/Nodes/Labels"
            connectivities_path = _find_first_dataset_path(h5, f"{part_path}/Elements", "Connectivities")
            labels_path = _find_first_dataset_path(h5, f"{part_path}/Elements", "Labels")

            missing_paths = [
                path
                for path in (nodes_path, connectivities_path, labels_path)
                if not path or path not in h5
            ]
            if missing_paths:
                raise StressCloudError(
                    f"stress h5 structure is not supported: missing {', '.join(missing_paths)} in {h5_path}; "
                    f"available top groups: {', '.join(h5.keys())}",
                )

            coordinates = np.asarray(h5[nodes_path][:], dtype=float)
            node_labels = np.asarray(h5[node_labels_path][:], dtype=int) if node_labels_path in h5 else np.arange(1, len(coordinates) + 1, dtype=int)
            connectivities = np.asarray(h5[connectivities_path][:], dtype=int)
            element_labels = np.asarray(h5[labels_path][:], dtype=int)
            if field_name == "stress":
                field_values = _read_element_stress_values(h5, part_name, len(connectivities), np) * stress_factor
                field_location = "element"
                field_unit = "Pa"
                field_label = "最大绝对应力"
                source_unit = stress_unit
                source_factor = stress_factor
                labels = element_labels
            else:
                field_values = _read_node_displacement_values(h5, part_name, len(coordinates), axis_name, np) * displacement_factor
                field_location = "node"
                field_unit = "m"
                field_label = _displacement_axis_label(axis_name)
                source_unit = displacement_unit
                source_factor = displacement_factor
                labels = node_labels
    except KeyError as error:
        raise StressCloudError(f"result h5 structure is not supported: {error}; file={h5_path}") from error

    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise StressCloudError("unexpected node coordinate shape")
    if connectivities.ndim != 2 or connectivities.shape[1] != 2:
        raise StressCloudError("unexpected element connectivity shape")

    value_min = float(field_values.min()) if len(field_values) else 0.0
    value_max = float(field_values.max()) if len(field_values) else 0.0
    if field_name == "stress":
        max_index = int(field_values.argmax()) if len(field_values) else -1
    else:
        max_index = int(np.argmax(np.abs(field_values))) if len(field_values) else -1

    bounds_min = coordinates.min(axis=0).astype(float).tolist()
    bounds_max = coordinates.max(axis=0).astype(float).tolist()
    max_value = float(field_values[max_index]) if max_index >= 0 else 0.0
    max_label = int(labels[max_index]) if max_index >= 0 and max_index < len(labels) else None
    field_payload = {
        "name": field_name,
        "axis": axis_name,
        "label": field_label,
        "location": field_location,
        "unit": field_unit,
        "source_unit": source_unit,
        "source_unit_factor": source_factor,
        "values": field_values.astype(float).round(9).tolist(),
        "min": value_min,
        "max": value_max,
    }

    payload = {
        "source": str(h5_path),
        "unit": field_unit,
        "source_unit": stress_unit,
        "source_unit_factor_to_pa": stress_factor,
        "nodes": coordinates.astype(float).round(6).tolist(),
        "elements": connectivities.astype(int).tolist(),
        "element_labels": element_labels.astype(int).tolist(),
        "field": field_payload,
        "bounds": {
            "min": bounds_min,
            "max": bounds_max,
        },
        "max_value": {
            "value": max_value,
            "index": max_index,
            "label": max_label,
            "location": field_location,
        },
    }
    if field_name == "stress":
        payload["stress"] = {
            "values": field_values.astype(float).round(6).tolist(),
            "min": value_min,
            "max": value_max,
        }
        payload["max_stress"] = {
            "value": value_max,
            "element_index": max_index,
            "element_label": max_label,
        }
    return payload


def _read_element_stress_values(h5: Any, part_name: str, element_count: int, np: Any) -> Any:
    base_path = _find_stress_element_class_path(h5, part_name)
    if not base_path:
        raise StressCloudError(
            f"stress dataset not found in h5; expected S data under /Steps for part {part_name}",
        )

    values = np.zeros(element_count, dtype=float)
    group = h5[base_path]
    for location_name in group:
        real_path = f"{base_path}/{location_name}/Real"
        if real_path not in h5:
            continue
        real = np.asarray(h5[real_path][:], dtype=float)
        if real.shape[0] != element_count:
            continue
        location_abs = np.max(np.abs(real), axis=1)
        values = np.maximum(values, location_abs)
    return values


def _read_node_displacement_values(h5: Any, part_name: str, node_count: int, axis: str, np: Any) -> Any:
    real_path = _find_step_field_real_path(h5, part_name, "U")
    if not real_path:
        raise StressCloudError(
            f"displacement dataset not found in h5; expected U data under /Steps for part {part_name}",
        )

    real = np.asarray(h5[real_path][:], dtype=float)
    if real.ndim != 2 or real.shape[0] != node_count or real.shape[1] < 3:
        raise StressCloudError(f"unexpected displacement shape at {real_path}: {real.shape}")

    if axis == "x":
        return real[:, 0]
    if axis == "y":
        return real[:, 1]
    if axis == "z":
        return real[:, 2]
    return np.linalg.norm(real[:, :3], axis=1)


def _find_mesh_part_name(h5: Any) -> str:
    if "/Parts" not in h5:
        return ""

    fallback = ""
    for part_name in h5["/Parts"]:
        part_path = f"/Parts/{part_name}"
        if not fallback:
            fallback = str(part_name)
        if (
            f"{part_path}/Nodes/Coordinates" in h5
            and _find_first_dataset_path(h5, f"{part_path}/Elements", "Connectivities")
            and _find_first_dataset_path(h5, f"{part_path}/Elements", "Labels")
        ):
            return str(part_name)
    return fallback


def _find_first_dataset_path(h5: Any, group_path: str, dataset_name: str) -> str:
    if group_path not in h5:
        return ""

    found_path = ""

    def visitor(name: str, obj: Any) -> None:
        nonlocal found_path
        if found_path:
            return
        if name.endswith(f"/{dataset_name}") or name == dataset_name:
            found_path = f"{group_path}/{name}"

    h5[group_path].visititems(visitor)
    return found_path


def _find_stress_element_class_path(h5: Any, part_name: str) -> str:
    steps_path = "/Steps"
    if steps_path not in h5:
        return ""

    candidates: list[str] = []

    def visitor(name: str, obj: Any) -> None:
        path = f"{steps_path}/{name}"
        if "/S/" not in path or not path.endswith("ElementClass:0"):
            return
        if f"/{part_name}-" in path or f"/{part_name}/" in path:
            candidates.append(path)

    h5[steps_path].visititems(visitor)
    if candidates:
        return candidates[0]

    fallback_candidates: list[str] = []

    def fallback_visitor(name: str, obj: Any) -> None:
        path = f"{steps_path}/{name}"
        if "/S/" in path and path.endswith("ElementClass:0"):
            fallback_candidates.append(path)

    h5[steps_path].visititems(fallback_visitor)
    return fallback_candidates[0] if fallback_candidates else ""


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


def _normalize_field_axis(field: str, axis: str) -> tuple[str, str]:
    normalized_field = field.strip().lower()
    normalized_axis = axis.strip().lower()
    if normalized_field in {"stress", "s"}:
        return "stress", "magnitude"
    if normalized_field not in {"displacement", "u"}:
        raise StressCloudError(f"unsupported cloud field: {field}")
    if normalized_axis not in {"x", "y", "z", "magnitude"}:
        raise StressCloudError(f"unsupported displacement axis: {axis}")
    return "displacement", normalized_axis


def _displacement_axis_label(axis: str) -> str:
    if axis == "x":
        return "X 方向位移"
    if axis == "y":
        return "Y 方向位移"
    if axis == "z":
        return "Z 方向位移"
    return "位移模长"


def _detect_stress_unit(h5_path: Path) -> str:
    name = h5_path.name.lower()
    if "mpa" in name:
        return "MPa"
    if "pa" in name:
        return "Pa"

    parent_name = h5_path.parent.name.lower()
    if "mpa" in parent_name:
        return "MPa"
    return "Pa"


def _detect_length_unit(h5_path: Path) -> str:
    name = h5_path.name.lower()
    parent_name = h5_path.parent.name.lower()
    for value in (name, parent_name):
        if "-mm-" in value or "(mm-" in value or "_mm_" in value:
            return "mm"
        if "-m-" in value or "(m-" in value or "_m_" in value:
            return "m"
    return "m"


def _stress_unit_to_pa_factor(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized == "mpa":
        return 1_000_000.0
    if normalized == "kpa":
        return 1_000.0
    return 1.0


def _length_unit_to_m_factor(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized == "mm":
        return 0.001
    return 1.0
