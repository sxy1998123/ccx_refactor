import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.core.config import settings
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
