import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pravburo_ref_common import models as application_models  # noqa: F401
from pravburo_ref_common.database import close_database
from starlette.middleware.sessions import SessionMiddleware

from src.api.v1.routes import router as api_v1_router
from src.core.config import get_settings
from src.core.logging import configure_logging
from src.core.security_headers import SecurityHeadersMiddleware
from src.integrations.legacy_lk.database import close_legacy_database
from src.site.legacy_routes import router as legacy_router
from src.web.routes.admin_2fa import router as admin_2fa_router
from src.web.routes.auth import router as auth_router
from src.web.routes.faq import router as faq_router
from src.web.routes.health import router as health_router
from src.web.routes.pages import router as pages_router
from src.web.routes.preview import router as preview_router
from src.web.routes.profile import router as profile_router
from src.web.routes.referrals import router as referrals_router

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Site service starting: environment=%s", settings.app_env)
    yield
    await close_database()
    await close_legacy_database()


app = FastAPI(
    title="pravburo-ref-site",
    debug=settings.app_debug,
    lifespan=lifespan,
    docs_url=None if settings.app_env == "production" else "/docs",
    redoc_url=None if settings.app_env == "production" else "/redoc",
    openapi_url=None if settings.app_env == "production" else "/openapi.json",
)
app.add_middleware(SecurityHeadersMiddleware, settings=settings)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.app_env == "production",
    max_age=settings.session_max_age_seconds,
)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).parents[1] / "web" / "static"),
    name="static",
)
app.include_router(health_router)
app.include_router(api_v1_router)
app.include_router(auth_router)
app.include_router(admin_2fa_router)
app.include_router(referrals_router)
app.include_router(faq_router)
app.include_router(profile_router)
app.include_router(legacy_router)
app.include_router(preview_router)
app.include_router(pages_router)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exception: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=exception)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
