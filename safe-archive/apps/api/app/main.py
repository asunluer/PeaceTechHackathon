"""FastAPI composition root."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes.auth import router as auth_router
from app.api.routes.cases import router as cases_router
from app.api.routes.reports import router as reports_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.export import router as export_router
from app.api.routes.health import router as health_router
from app.api.routes.users import router as users_router
from app.core.config import get_settings
from app.infrastructure.database import Database


@asynccontextmanager
async def lifespan(application: FastAPI):
    database = Database(get_settings())
    application.state.database = database
    try:
        yield
    finally:
        await database.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title="SAFE-ARCHIVE API",
        description="Structured preservation of publicly observable online content.",
        version="0.1.0",
        docs_url="/docs" if settings.environment != "production" else None,
        redoc_url=None,
        lifespan=lifespan,
    )
    application.include_router(health_router, prefix="/api/v1")
    application.include_router(auth_router, prefix="/api/v1")
    application.include_router(users_router, prefix="/api/v1")
    application.include_router(cases_router, prefix="/api/v1")
    application.include_router(reports_router, prefix="/api/v1")
    application.include_router(evidence_router, prefix="/api/v1")
    application.include_router(export_router, prefix="/api/v1")
    return application


app = create_app()
