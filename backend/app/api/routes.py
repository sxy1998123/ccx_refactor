import asyncio

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
from app.services.pointcloud_potree import PointCloudError, get_demo_manifest, get_demo_node_path

router = APIRouter()


class DemoAnalysisRequest(BaseModel):
    route_id: str


class DemoAnalysisResponse(BaseModel):
    status: str
    route_id: str
    message: str


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


@router.post("/api/demo/analysis-tasks", response_model=DemoAnalysisResponse, tags=["demo"])
async def submit_demo_analysis_task(request: DemoAnalysisRequest) -> DemoAnalysisResponse:
    await asyncio.sleep(3)
    route_id = request.route_id.strip() or "YX-2026-04-17"
    return DemoAnalysisResponse(
        status="completed",
        route_id=route_id,
        message="演示分析任务处理完成",
    )


@router.get("/api/demo/pointcloud/potree/manifest", tags=["pointcloud"])
def demo_pointcloud_manifest() -> dict:
    try:
        return get_demo_manifest()
    except PointCloudError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/api/demo/pointcloud/potree/nodes/{node_id}.bin", tags=["pointcloud"])
def demo_pointcloud_node(node_id: str) -> FileResponse:
    try:
        node_path = get_demo_node_path(node_id)
    except PointCloudError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error

    return FileResponse(node_path, media_type="application/octet-stream")
