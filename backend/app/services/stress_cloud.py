from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


class StressCloudError(RuntimeError):
    pass


@lru_cache(maxsize=8)
def get_stress_cloud_for_h5(h5_path: Path) -> dict[str, Any]:
    h5_path = Path(h5_path)
    if not h5_path.exists():
        raise StressCloudError(f"stress h5 not found: {h5_path}")

    try:
        import h5py
        import numpy as np
    except ImportError as error:
        raise StressCloudError(f"h5py/numpy is required to parse stress h5: {error}") from error

    stress_unit = _detect_stress_unit(h5_path)
    stress_factor = _stress_unit_to_pa_factor(stress_unit)

    try:
        with h5py.File(h5_path, "r") as h5:
            part_name = _find_mesh_part_name(h5)
            if not part_name:
                raise StressCloudError(f"stress h5 has no supported mesh part under /Parts: {h5_path}")

            part_path = f"/Parts/{part_name}"
            nodes_path = f"{part_path}/Nodes/Coordinates"
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
            connectivities = np.asarray(h5[connectivities_path][:], dtype=int)
            element_labels = np.asarray(h5[labels_path][:], dtype=int)
            stresses = _read_element_stress_values(h5, part_name, len(connectivities), np) * stress_factor
    except KeyError as error:
        raise StressCloudError(f"stress h5 structure is not supported: {error}; file={h5_path}") from error

    if coordinates.ndim != 2 or coordinates.shape[1] != 3:
        raise StressCloudError("unexpected node coordinate shape")
    if connectivities.ndim != 2 or connectivities.shape[1] != 2:
        raise StressCloudError("unexpected element connectivity shape")

    stress_min = float(stresses.min()) if len(stresses) else 0.0
    stress_max = float(stresses.max()) if len(stresses) else 0.0
    max_index = int(stresses.argmax()) if len(stresses) else -1

    bounds_min = coordinates.min(axis=0).astype(float).tolist()
    bounds_max = coordinates.max(axis=0).astype(float).tolist()

    return {
        "source": str(h5_path),
        "unit": "Pa",
        "source_unit": stress_unit,
        "source_unit_factor_to_pa": stress_factor,
        "nodes": coordinates.astype(float).round(6).tolist(),
        "elements": connectivities.astype(int).tolist(),
        "element_labels": element_labels.astype(int).tolist(),
        "stress": {
            "values": stresses.astype(float).round(6).tolist(),
            "min": stress_min,
            "max": stress_max,
        },
        "bounds": {
            "min": bounds_min,
            "max": bounds_max,
        },
        "max_stress": {
            "value": stress_max,
            "element_index": max_index,
            "element_label": int(element_labels[max_index]) if max_index >= 0 else None,
        },
    }


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


def _stress_unit_to_pa_factor(unit: str) -> float:
    normalized = unit.strip().lower()
    if normalized == "mpa":
        return 1_000_000.0
    if normalized == "kpa":
        return 1_000.0
    return 1.0
