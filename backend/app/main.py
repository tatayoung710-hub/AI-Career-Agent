"""API composition and operational health; database migrations run before startup."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app import auth, core_routes
from app.ai_routes import router as ai_router
from app.automation_routes import router as automation_router
from app.config import settings
from app.db import engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth.router, prefix="/api/v1")
app.include_router(core_routes.router, prefix="/api/v1")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(automation_router, prefix="/api/v1")


@app.get("/api/v1/health", tags=["Operations"])
@app.get("/health", include_in_schema=False)
def health() -> dict:
    warnings = []
    if not settings.openai_api_key:
        warnings.append("尚未配置 OpenAI API；AI 功能会明确返回配置错误")
    if settings.database_url.startswith("sqlite"):
        warnings.append("SQLite 仅用于单 Worker 本地开发；生产环境需 PostgreSQL")
    if settings.jwt_secret.startswith("development-only"):
        warnings.append("当前使用本地开发 JWT 密钥，部署前请设置 JWT_SECRET")
    database_ready = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            database_ready = inspect(connection).has_table("users")
    except SQLAlchemyError:
        warnings.append("数据库暂不可访问")
    if not database_ready:
        warnings.append("数据库尚未就绪，请检查连接并运行 Alembic 迁移")
    return {
        "status": "ok" if database_ready else "degraded",
        "database_ready": database_ready,
        "ai_configured": bool(settings.openai_api_key),
        "warnings": warnings,
    }
