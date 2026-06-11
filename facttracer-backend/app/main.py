from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi import HTTPException as FastAPIHTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin, auth, health, issues, podcasts, users
from app.core.config import get_settings
from app.core.rate_limit import rate_limit_middleware
from app.db.schema import ensure_database_schema
from app.db.session import SessionLocal, engine
from app.services.bootstrap.defaults import bootstrap_default_discovery
from app.services.scheduler.runtime import embedded_scheduler, embedded_worker


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ensure_database_schema(engine)
    db = SessionLocal()
    try:
        bootstrap_default_discovery(db)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
    embedded_scheduler.start()
    embedded_worker.start()
    try:
        yield
    finally:
        embedded_worker.stop()
        embedded_scheduler.stop()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_headers=["*"],
        allow_methods=["*"],
        allow_origins=settings.cors_origins,
    )
    app.middleware("http")(rate_limit_middleware)

    @app.exception_handler(FastAPIHTTPException)
    async def http_exception_handler(_: Request, exc: FastAPIHTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            message = exc.detail.get("message", "요청을 처리하지 못했습니다.")
            code = exc.detail.get("code", "REQUEST_ERROR")
            details = exc.detail.get("details", {})
        else:
            message = str(exc.detail) if exc.detail else "요청을 처리하지 못했습니다."
            code = "REQUEST_ERROR"
            details = {}
        return JSONResponse(
            status_code=exc.status_code,
            content={"message": message, "code": code, "details": details},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "message": "입력한 내용을 다시 확인해 주세요.",
                "code": "VALIDATION_ERROR",
                "details": {"errors": exc.errors()},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "message": "일시적으로 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.",
                "code": "INTERNAL_ERROR",
                "details": {},
            },
        )

    app.include_router(health.router)
    app.include_router(auth.router, prefix=settings.api_prefix)
    app.include_router(users.router, prefix=settings.api_prefix)
    app.include_router(issues.router, prefix=settings.api_prefix)
    app.include_router(podcasts.router, prefix=settings.api_prefix)
    app.include_router(admin.router, prefix=settings.api_prefix)
    return app


app = create_app()
