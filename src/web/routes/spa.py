"""Serves the built React app (frontend/dist) for the routes already migrated to it.

Every page of the site is a React route: ``SPA_PATHS`` and ``SPA_PATH_TEMPLATES`` list them and
each answers with the built ``index.html``. Without a build (tests, plain dev) no page routes are
registered and only the API works; the app logs a warning about it at startup.
"""

import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

FRONTEND_DIST = Path(
    os.environ.get("FRONTEND_DIST") or Path(__file__).parents[3] / "frontend" / "dist"
)
INDEX_FILE = FRONTEND_DIST / "index.html"

SPA_PATHS = (
    "/",
    "/faq",
    "/login",
    "/register",
    "/register/confirm",
    "/password/reset",
    "/password/reset/confirm",
    "/onboarding",
    "/cabinet",
    "/cabinet/visits",
    "/cabinet/applications",
    "/payouts",
    "/profile",
    "/admin",
    "/admin/applications",
    "/admin/partners",
    "/admin/network/rates",
    "/admin/network/tree",
    "/admin/faq",
    "/admin/payouts",
    "/admin/2fa/setup",
    "/admin/2fa/verify",
)

# Paths with parameters, in Starlette syntax. The frontend lists the same routes in React
# Router syntax (`:name`); see frontend/src/app/spaRoutes.ts.
SPA_PATH_TEMPLATES = (
    "/r/{referral_code:uuid}",
    "/r/{referral_code:uuid}/success",
)


def build_spa_router(index_file: Path = INDEX_FILE) -> APIRouter | None:
    if not index_file.is_file():
        return None
    router = APIRouter(tags=["spa"], include_in_schema=False)

    async def index() -> FileResponse:
        # index.html references hashed assets: it must never be cached itself.
        return FileResponse(index_file, headers={"Cache-Control": "no-cache"})

    for path in (*SPA_PATHS, *SPA_PATH_TEMPLATES):
        router.add_api_route(path, index, methods=["GET"])
    return router
