from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
from app.db.connection import (
    delete_database_record,
    get_schema_descriptions,
    insert_database_record,
    list_database_records,
)
from app.schemas.app_info import AppInfo
from app.schemas.health import HealthCheck
from app.services.pointcloud_potree import (
    PointCloudError,
    cache_key_for_source,
    get_manifest_for_source,
    get_node_path_for_source,
)
from app.services.preprocess import (
    PreprocessTaskNotFound,
    get_preprocess_result,
    get_preprocess_task,
    submit_preprocess_task,
)
from app.services.stress_cloud import StressCloudError, get_stress_cloud_for_h5

router = APIRouter()


class DatabaseRecordRequest(BaseModel):
    values: dict[str, object]


class DatabaseRecordResponse(BaseModel):
    table_name: str
    rowid: int
    message: str


class DatabaseDeleteResponse(BaseModel):
    table_name: str
    rowid: int
    message: str


class PreprocessTaskRequest(BaseModel):
    route_id: str
    tower_type: str
    inp_file: str
    tower_txt_files: dict[str, str]
    env_txt_file: str
    image_files: list[str] = []
    point_cloud_files: list[str] = []


class PreprocessTaskResponse(BaseModel):
    task_id: str
    status: str
    route_id: str
    tower_type: str
    inp_file: str
    created_at: str
    updated_at: str
    message: str
    result_url: str


@router.get("/health", response_model=HealthCheck, tags=["system"])
def health_check() -> HealthCheck:
    return HealthCheck(status="ok", service=settings.app_name)


@router.get("/api/app-info", response_model=AppInfo, tags=["system"])
def app_info() -> AppInfo:
    return AppInfo(
        app_name=settings.app_name,
        version=settings.version,
        environment=settings.environment,
    )


@router.get("/api/database/schema", tags=["database"])
def database_schema() -> dict:
    return get_schema_descriptions()


@router.get("/api/database/{table_name}/records", tags=["database"])
def database_records(table_name: str, limit: int = 20) -> dict:
    try:
        return list_database_records(table_name, limit)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/api/database/{table_name}/records", response_model=DatabaseRecordResponse, tags=["database"])
def create_database_record(table_name: str, request: DatabaseRecordRequest) -> DatabaseRecordResponse:
    try:
        result = insert_database_record(table_name, request.values)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return DatabaseRecordResponse(
        table_name=result["table_name"],
        rowid=result["rowid"],
        message="数据录入成功",
    )


@router.delete("/api/database/{table_name}/records/{rowid}", response_model=DatabaseDeleteResponse, tags=["database"])
def remove_database_record(table_name: str, rowid: int) -> DatabaseDeleteResponse:
    try:
        result = delete_database_record(table_name, rowid)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except LookupError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return DatabaseDeleteResponse(
        table_name=result["table_name"],
        rowid=result["rowid"],
        message="数据删除成功",
    )


@router.post("/api/preprocess/tasks", response_model=PreprocessTaskResponse, tags=["preprocess"])
def create_preprocess_task(request: PreprocessTaskRequest) -> PreprocessTaskResponse:
    payload = request.model_dump()
    route_id = payload["route_id"].strip()
    if not route_id:
        raise HTTPException(status_code=400, detail="线路号不能为空")
    payload["route_id"] = route_id

    if set(payload["tower_txt_files"]) != {"tower1", "tower2", "tower3", "tower4"}:
        raise HTTPException(status_code=400, detail="必须提交 tower1/tower2/tower3/tower4 四个塔基端 TXT 文件")

    return PreprocessTaskResponse(**submit_preprocess_task(payload))


@router.get("/api/preprocess/tasks/{task_id}", response_model=PreprocessTaskResponse, tags=["preprocess"])
def preprocess_task_status(task_id: str) -> PreprocessTaskResponse:
    try:
        return PreprocessTaskResponse(**get_preprocess_task(task_id))
    except PreprocessTaskNotFound as error:
        raise HTTPException(status_code=404, detail="预处理任务不存在") from error


@router.get("/api/preprocess/tasks/{task_id}/result", tags=["preprocess"])
def preprocess_task_result(task_id: str) -> dict:
    try:
        return get_preprocess_result(task_id)
    except PreprocessTaskNotFound as error:
        raise HTTPException(status_code=404, detail="预处理结果不存在") from error


@router.get("/api/preprocess/tasks/{task_id}/pointcloud/potree/manifest", tags=["pointcloud"])
def preprocess_pointcloud_manifest(task_id: str) -> dict:
    try:
        result = get_preprocess_result(task_id)
        source_path = _first_point_cloud_path(result)
        prefix = f"/api/preprocess/tasks/{task_id}/pointcloud/potree/nodes"
        return get_manifest_for_source(source_path, cache_key_for_source(task_id, source_path), prefix)
    except PreprocessTaskNotFound as error:
        raise HTTPException(status_code=404, detail="预处理任务不存在") from error
    except PointCloudError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/api/preprocess/tasks/{task_id}/pointcloud/potree/nodes/{node_id}.bin", tags=["pointcloud"])
def preprocess_pointcloud_node(task_id: str, node_id: str) -> FileResponse:
    try:
        result = get_preprocess_result(task_id)
        source_path = _first_point_cloud_path(result)
        prefix = f"/api/preprocess/tasks/{task_id}/pointcloud/potree/nodes"
        node_path = get_node_path_for_source(source_path, cache_key_for_source(task_id, source_path), node_id, prefix)
    except PreprocessTaskNotFound as error:
        raise HTTPException(status_code=404, detail="预处理任务不存在") from error
    except PointCloudError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return FileResponse(node_path, media_type="application/octet-stream")


@router.get("/api/risk/base-stress-cloud", tags=["risk"])
def base_stress_cloud() -> dict:
    try:
        return get_stress_cloud_for_h5(settings.base_stress_h5_path)
    except StressCloudError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


def _first_point_cloud_path(result: dict) -> str:
    point_cloud_files = result.get("inputs", {}).get("point_cloud_files", [])
    if not point_cloud_files:
        raise PointCloudError("No point cloud file was submitted for this task")
    return str(point_cloud_files[0])
