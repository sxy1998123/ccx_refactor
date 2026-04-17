from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from threading import Lock
from typing import Any

import numpy as np

DEMO_POINTCLOUD_NAME = "geomap_20260321_122228.pcd"
MANIFEST_NAME = "manifest.json"
NODE_FORMAT = "float32x3+uint32rgb"
POINT_STRIDE_BYTES = 16
ROOT_POINT_LIMIT = 120_000
LEVEL_ONE_POINT_LIMIT = 80_000
LEVEL_TWO_POINT_LIMIT = 25_000

_build_lock = Lock()


class PointCloudError(RuntimeError):
    pass


def get_demo_pointcloud_source() -> Path:
    configured_path = os.getenv("CCX_DEMO_POINTCLOUD")
    if configured_path:
        return Path(configured_path).expanduser().resolve()

    backend_root = Path(__file__).resolve().parents[2]
    return backend_root / "pointcloud_demo" / DEMO_POINTCLOUD_NAME


def get_potree_cache_dir() -> Path:
    data_dir = Path(os.getenv("CCX_DATA_DIR", Path.cwd() / ".ccx-data")).expanduser().resolve()
    return data_dir / "pointcloud_cache" / "demo_potree_v1"


def get_demo_manifest() -> dict[str, Any]:
    source_path = get_demo_pointcloud_source()
    cache_dir = get_potree_cache_dir()

    if not source_path.exists():
        raise PointCloudError(f"Demo point cloud file not found: {source_path}")

    with _build_lock:
        manifest = _load_cached_manifest(cache_dir, source_path)
        if manifest is None:
            manifest = _build_demo_cache(source_path, cache_dir)

    return _with_absolute_node_urls(manifest)


def get_demo_node_path(node_id: str) -> Path:
    if not node_id or any(char not in "r01234567" for char in node_id) or not node_id.startswith("r"):
        raise PointCloudError(f"Invalid point cloud node id: {node_id}")

    node_path = get_potree_cache_dir() / "nodes" / f"{node_id}.bin"
    if not node_path.exists():
        get_demo_manifest()

    if not node_path.exists():
        raise PointCloudError(f"Point cloud node not found: {node_id}")

    return node_path


def _load_cached_manifest(cache_dir: Path, source_path: Path) -> dict[str, Any] | None:
    manifest_path = cache_dir / MANIFEST_NAME
    if not manifest_path.exists():
        return None

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None

    stat = source_path.stat()
    source_info = manifest.get("source", {})
    if source_info.get("size") != stat.st_size or source_info.get("mtime_ns") != stat.st_mtime_ns:
        return None

    nodes = manifest.get("nodes", [])
    if not nodes:
        return None

    for node in nodes:
        path = cache_dir / "nodes" / f"{node.get('id')}.bin"
        if not path.exists():
            return None

    return manifest


def _build_demo_cache(source_path: Path, cache_dir: Path) -> dict[str, Any]:
    tmp_dir = cache_dir.with_name(f"{cache_dir.name}.tmp")
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_nodes_dir = tmp_dir / "nodes"
    tmp_nodes_dir.mkdir(parents=True, exist_ok=True)

    header = _read_pcd_header(source_path)
    points = _open_supported_pcd(source_path, header)
    finite_indices, bounds_min, bounds_max = _prepare_bounds(points)
    level_one_codes, level_two_codes = _build_octree_codes(points, finite_indices, bounds_min, bounds_max)

    nodes: list[dict[str, Any]] = []
    nodes.append(
        _write_node(
            node_id="r",
            depth=0,
            indices=finite_indices,
            point_limit=ROOT_POINT_LIMIT,
            points=points,
            bounds_min=bounds_min,
            bounds_max=bounds_max,
            nodes_dir=tmp_nodes_dir,
        )
    )

    for child in range(8):
        node_indices = finite_indices[level_one_codes == child]
        if node_indices.size == 0:
            continue
        node_min, node_max = _node_bounds(bounds_min, bounds_max, f"r{child}")
        nodes.append(
            _write_node(
                node_id=f"r{child}",
                depth=1,
                indices=node_indices,
                point_limit=LEVEL_ONE_POINT_LIMIT,
                points=points,
                bounds_min=node_min,
                bounds_max=node_max,
                nodes_dir=tmp_nodes_dir,
            )
        )

    leaf_codes = level_one_codes.astype(np.uint16) * 8 + level_two_codes.astype(np.uint16)
    for leaf in range(64):
        node_indices = finite_indices[leaf_codes == leaf]
        if node_indices.size == 0:
            continue
        parent = leaf // 8
        child = leaf % 8
        node_id = f"r{parent}{child}"
        node_min, node_max = _node_bounds(bounds_min, bounds_max, node_id)
        nodes.append(
            _write_node(
                node_id=node_id,
                depth=2,
                indices=node_indices,
                point_limit=LEVEL_TWO_POINT_LIMIT,
                points=points,
                bounds_min=node_min,
                bounds_max=node_max,
                nodes_dir=tmp_nodes_dir,
            )
        )

    stat = source_path.stat()
    manifest = {
        "version": 1,
        "name": "demo_potree_pointcloud",
        "source": {
            "file": str(source_path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "points": int(header["points"]),
            "fields": header["fields"],
            "data": header["data"],
        },
        "pointFormat": NODE_FORMAT,
        "pointStrideBytes": POINT_STRIDE_BYTES,
        "bounds": {"min": _to_float_list(bounds_min), "max": _to_float_list(bounds_max)},
        "nodes": nodes,
        "totalVisiblePoints": int(sum(node["pointCount"] for node in nodes)),
    }

    (tmp_dir / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    if cache_dir.exists():
        shutil.rmtree(cache_dir)
    tmp_dir.replace(cache_dir)
    return manifest


def _read_pcd_header(source_path: Path) -> dict[str, Any]:
    header: dict[str, Any] = {}
    header_lines: list[str] = []
    offset = 0

    with source_path.open("rb") as file:
        while True:
            line = file.readline()
            if not line:
                raise PointCloudError("PCD header ended before DATA line")

            offset += len(line)
            text = line.decode("ascii", errors="strict").strip()
            header_lines.append(text)
            if text.startswith("#") or not text:
                continue

            parts = text.split()
            key = parts[0].lower()
            values = parts[1:]
            if key == "data":
                header["data"] = values[0].lower()
                break
            header[key] = values

    header["data_offset"] = offset
    header["header_lines"] = header_lines
    header["fields"] = header.get("fields", [])
    header["points"] = int(header.get("points", header.get("width", ["0"]))[0])
    return header


def _open_supported_pcd(source_path: Path, header: dict[str, Any]) -> np.memmap:
    fields = header.get("fields", [])
    sizes = [int(value) for value in header.get("size", [])]
    types = header.get("type", [])
    counts = [int(value) for value in header.get("count", [])]

    expected_fields = ["x", "y", "z", "rgb"]
    if fields != expected_fields or sizes != [4, 4, 4, 4] or types != ["F", "F", "F", "F"] or counts != [1, 1, 1, 1]:
        raise PointCloudError(
            "Only binary PCD with FIELDS x y z rgb, SIZE 4 4 4 4, TYPE F F F F is supported for the demo route"
        )
    if header.get("data") != "binary":
        raise PointCloudError("Only DATA binary PCD files are supported for the demo route")

    dtype = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("rgb", "<f4")])
    return np.memmap(source_path, dtype=dtype, mode="r", offset=int(header["data_offset"]), shape=(int(header["points"]),))


def _prepare_bounds(points: np.memmap) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    finite = np.isfinite(points["x"]) & np.isfinite(points["y"]) & np.isfinite(points["z"])
    finite_indices = np.flatnonzero(finite)
    if finite_indices.size == 0:
        raise PointCloudError("Point cloud contains no finite XYZ points")

    mins = np.array(
        [
            float(np.min(points["x"][finite])),
            float(np.min(points["y"][finite])),
            float(np.min(points["z"][finite])),
        ],
        dtype=np.float32,
    )
    maxs = np.array(
        [
            float(np.max(points["x"][finite])),
            float(np.max(points["y"][finite])),
            float(np.max(points["z"][finite])),
        ],
        dtype=np.float32,
    )
    span = np.maximum(maxs - mins, np.float32(0.001))
    padding = np.float32(max(float(np.max(span)) * 0.01, 0.001))
    return finite_indices, mins - padding, maxs + padding


def _build_octree_codes(
    points: np.memmap,
    finite_indices: np.ndarray,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    span = np.maximum(bounds_max - bounds_min, np.float32(0.001))
    qx = np.clip(((points["x"][finite_indices] - bounds_min[0]) / span[0] * 4).astype(np.uint8), 0, 3)
    qy = np.clip(((points["y"][finite_indices] - bounds_min[1]) / span[1] * 4).astype(np.uint8), 0, 3)
    qz = np.clip(((points["z"][finite_indices] - bounds_min[2]) / span[2] * 4).astype(np.uint8), 0, 3)

    level_one = ((qx >> 1) | ((qy >> 1) << 1) | ((qz >> 1) << 2)).astype(np.uint8)
    level_two = ((qx & 1) | ((qy & 1) << 1) | ((qz & 1) << 2)).astype(np.uint8)
    return level_one, level_two


def _write_node(
    *,
    node_id: str,
    depth: int,
    indices: np.ndarray,
    point_limit: int,
    points: np.memmap,
    bounds_min: np.ndarray,
    bounds_max: np.ndarray,
    nodes_dir: Path,
) -> dict[str, Any]:
    selected = _sample_indices(indices, point_limit)
    output_dtype = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("rgb", "<u4")])
    output = np.empty(selected.size, dtype=output_dtype)
    output["x"] = points["x"][selected]
    output["y"] = points["y"][selected]
    output["z"] = points["z"][selected]
    output["rgb"] = np.asarray(points["rgb"][selected], dtype=np.float32).view(np.uint32)

    node_path = nodes_dir / f"{node_id}.bin"
    output.tofile(node_path)

    return {
        "id": node_id,
        "depth": depth,
        "pointCount": int(selected.size),
        "sourcePointCount": int(indices.size),
        "byteSize": int(node_path.stat().st_size),
        "bounds": {"min": _to_float_list(bounds_min), "max": _to_float_list(bounds_max)},
        "url": f"/api/demo/pointcloud/potree/nodes/{node_id}.bin",
    }


def _sample_indices(indices: np.ndarray, point_limit: int) -> np.ndarray:
    if indices.size <= point_limit:
        return indices

    sampled_offsets = np.linspace(0, indices.size - 1, point_limit, dtype=np.int64)
    return indices[sampled_offsets]


def _node_bounds(root_min: np.ndarray, root_max: np.ndarray, node_id: str) -> tuple[np.ndarray, np.ndarray]:
    node_min = root_min.astype(np.float32).copy()
    node_max = root_max.astype(np.float32).copy()

    for char in node_id[1:]:
        child = int(char)
        midpoint = (node_min + node_max) / np.float32(2.0)
        if child & 1:
            node_min[0] = midpoint[0]
        else:
            node_max[0] = midpoint[0]
        if child & 2:
            node_min[1] = midpoint[1]
        else:
            node_max[1] = midpoint[1]
        if child & 4:
            node_min[2] = midpoint[2]
        else:
            node_max[2] = midpoint[2]

    return node_min, node_max


def _to_float_list(values: np.ndarray) -> list[float]:
    return [float(value) for value in values]


def _with_absolute_node_urls(manifest: dict[str, Any]) -> dict[str, Any]:
    copied = dict(manifest)
    copied["nodes"] = [dict(node) for node in manifest.get("nodes", [])]
    for node in copied["nodes"]:
        node["url"] = f"/api/demo/pointcloud/potree/nodes/{node['id']}.bin"
    return copied
