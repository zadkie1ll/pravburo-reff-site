"""Local equivalent of nginx's bounty routes, enabled explicitly in development."""

import httpx
from fastapi import APIRouter, Request, Response

from src.core.config import get_settings

router = APIRouter()
HOP_HEADERS = {"connection", "transfer-encoding", "content-length", "content-encoding"}


@router.api_route("/admin/rewards", methods=["GET", "POST"])
@router.api_route("/admin/rewards/{rest:path}", methods=["GET", "POST"])
@router.api_route("/admin/reward-rates", methods=["GET", "POST"])
@router.api_route("/admin/reward-rates/{rest:path}", methods=["GET", "POST"])
@router.api_route("/admin/partner-levels", methods=["GET", "POST"])
@router.api_route("/admin/partner-levels/{rest:path}", methods=["GET", "POST"])
@router.get("/admin/static/{rest:path}")
async def forward(request: Request) -> Response:
    settings = get_settings()
    if settings.app_env != "development" or settings.dev_bounty_port is None:
        return Response(status_code=404)
    url = f"http://127.0.0.1:{settings.dev_bounty_port}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                url,
                # Keep the original host so generated links remain on the site.
                headers={k: v for k, v in request.headers.items() if k not in HOP_HEADERS},
                content=await request.body(),
            )
    except httpx.RequestError:
        return Response(
            "Локальный сервис начислений не запущен.",
            status_code=503,
            media_type="text/plain",
        )
    return Response(
        upstream.content,
        status_code=upstream.status_code,
        headers={k: v for k, v in upstream.headers.items() if k not in HOP_HEADERS},
    )
