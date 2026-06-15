from contextlib import asynccontextmanager

import sentry_sdk
import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

from app.config import settings
from app.routers import auth, catalogue, health, inventory, orders, shopify
from app.routers import forecasts as forecasts_router
from app.routers import recommendations as recommendations_router
from app.routers import settings as settings_router
from app.routers import sync as sync_router

structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        {"debug": 10, "info": 20, "warning": 30, "error": 40}.get(settings.log_level, 20)
    ),
)
log = structlog.get_logger()

if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        integrations=[FastApiIntegration(), SqlalchemyIntegration()],
        traces_sample_rate=0.1,
    )


def _check_startup_config() -> None:
    """Log warnings for missing env vars at startup so operators notice immediately."""
    shopify_missing = settings.validate_required_for_shopify()
    auth_missing = settings.validate_required_for_auth()

    if shopify_missing:
        log.warning(
            "startup_config_missing_shopify",
            missing=shopify_missing,
            hint="Shopify OAuth will fail until these are set.",
        )
    if auth_missing:
        log.error(
            "startup_config_insecure_auth",
            missing=auth_missing,
            hint="Auth secrets are too short — set secure random values before accepting traffic.",
        )


@asynccontextmanager
async def _lifespan(app: FastAPI):  # noqa: ARG001
    _check_startup_config()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ThreadOS API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=_lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_url],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        log.info("request", method=request.method, path=request.url.path)
        response = await call_next(request)
        log.info("response", status=response.status_code)
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception):
        log.error("unhandled_error", error=str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(shopify.router)
    app.include_router(catalogue.router)
    app.include_router(orders.router)
    app.include_router(inventory.router)
    app.include_router(sync_router.router)
    app.include_router(forecasts_router.router)
    app.include_router(recommendations_router.router)
    app.include_router(settings_router.router)

    return app


app = create_app()
