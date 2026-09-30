import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pravburo_ref_common import models as application_models  # noqa: F401
from pravburo_ref_common.database import close_database
from starlette.middleware.sessions import SessionMiddleware

from src.api.v1.routes import router as api_v1_router
from src.core.config import get_settings
from src.core.logging import configure_logging
from src.core.scheduler import create_scheduler
from src.core.security_headers import SecurityHeadersMiddleware
from src.integrations.legacy_lk.database import close_legacy_database
from src.site.legacy_routes import router as legacy_router
from src.web.api_errors import ApiError, api_error_handler, validation_error_handler
from src.web.routes.admin_2fa import router as admin_2fa_router
from src.web.routes.api_admin import router as api_admin_router
from src.web.routes.api_admin_2fa import router as api_admin_2fa_router
from src.web.routes.api_admin_applications import router as api_admin_applications_router
from src.web.routes.api_admin_faq import router as api_admin_faq_router
from src.web.routes.api_admin_network import router as api_admin_network_router
from src.web.routes.api_admin_partners import router as api_admin_partners_router
from src.web.routes.api_admin_payouts import router as api_admin_payouts_router
from src.web.routes.api_auth import router as api_auth_router
from src.web.routes.api_cabinet import router as api_cabinet_router
from src.web.routes.api_onboarding import router as api_onboarding_router
from src.web.routes.api_payouts import router as api_payouts_router
from src.web.routes.api_profile import router as api_profile_router
from src.web.routes.api_referral import router as api_referral_router
from src.web.routes.api_site import router as api_site_router
from src.web.routes.auth import router as auth_router
from src.web.routes.health import router as health_router
from src.web.routes.internal import router as internal_router
from src.web.routes.pages import router as pages_router
from src.web.routes.payouts import router as payouts_router
from src.web.routes.push import router as push_router
from src.web.routes.referrals import router as referrals_router
from src.web.routes.spa import FRONTEND_DIST, build_spa_router

settings = get_settings()
configure_logging(settings)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("Site service starting: environment=%s", settings.app_env)
    scheduler = create_scheduler()
    scheduler.start()
    yield
    scheduler.shutdown()
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
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
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
if (FRONTEND_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")
app.include_router(health_router)
app.include_router(api_v1_router)
app.include_router(api_site_router)
app.include_router(api_admin_router)
app.include_router(api_admin_applications_router)
app.include_router(api_admin_partners_router)
app.include_router(api_admin_network_router)
app.include_router(api_admin_faq_router)
app.include_router(api_admin_payouts_router)
app.include_router(api_admin_2fa_router)
app.include_router(api_auth_router)
app.include_router(api_onboarding_router)
app.include_router(api_cabinet_router)
app.include_router(api_payouts_router)
app.include_router(api_profile_router)
app.include_router(api_referral_router)
# The site's pages: the React app (index.html) for every page route listed in spa.py.
spa_router = build_spa_router()
if spa_router is not None:
    app.include_router(spa_router)
else:
    logger.warning(
        "Frontend build not found at %s: the site pages are not served, only the API. "
        "Build it with `npm run build` in frontend/ (the Docker image does this).",
        FRONTEND_DIST,
    )
app.include_router(auth_router)
app.include_router(admin_2fa_router)
app.include_router(internal_router)
app.include_router(referrals_router)
app.include_router(push_router)
app.include_router(payouts_router)
app.include_router(legacy_router)
app.include_router(pages_router)


@app.exception_handler(Exception)
async def unhandled_error(_: Request, exception: Exception) -> JSONResponse:
    logger.exception("Unhandled request error", exc_info=exception)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
