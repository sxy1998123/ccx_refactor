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

    with h5py.File(h5_path, "r") as h5:
        coordinates = np.asarray(h5["/Parts/TOWER1/Nodes/Coordinates"][:], dtype=float)
        connectivities = np.asarray(h5["/Parts/TOWER1/Elements/ElementClass:0/Connectivities"][:], dtype=int)
        element_labels = np.asarray(h5["/Parts/TOWER1/Elements/ElementClass:0/Labels"][:], dtype=int)
        stresses = _read_element_stress_values(h5, len(connectivities), np)

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


def _read_element_stress_values(h5: Any, element_count: int, np: Any) -> Any:
    base_path = "/Steps/Step-1/Frames/Frame:0/S/TOWER1-1/ElementClass:0"
    if base_path not in h5:
        raise StressCloudError("stress dataset not found in h5")

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
