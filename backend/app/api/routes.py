from fastapi import APIRouter

from app.core.config import settings
from app.schemas.app_info import AppInfo
from app.schemas.health import HealthCheck

router = APIRouter()


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

