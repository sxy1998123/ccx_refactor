import uvicorn

from app.core.config import settings
from app.core.logging import LOGGING_CONFIG, configure_logging, get_logger


def main() -> None:
    configure_logging()
    logger = get_logger("app.run")
    logger.info(
        "starting backend host=%s port=%s reload=%s env=%s",
        settings.host,
        settings.port,
        settings.reload,
        settings.environment,
    )
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_config=LOGGING_CONFIG,
    )


if __name__ == "__main__":
    main()
