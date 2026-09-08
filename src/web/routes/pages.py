from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from src.api.dependencies import LegacyGatewayDependency
from src.core.config import Settings, get_settings
from src.web.dependencies import CurrentAdmin

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=Path(__file__).parents[1] / "templates")
SettingsDependency = Annotated[Settings, Depends(get_settings)]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request, settings: SettingsDependency) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.app_name},
    )


@router.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    # Served at root (not under /static) so its default registration scope
    # covers the whole origin, not just /static/*.
    static_dir = Path(__file__).parents[1] / "static"
    return FileResponse(static_dir / "sw.js", media_type="application/javascript")


@router.get("/dev/clients/{client_id}", response_class=HTMLResponse)
async def development_client_dashboard(
    request: Request,
    client_id: int,
    gateway: LegacyGatewayDependency,
    settings: SettingsDependency,
    _admin: CurrentAdmin,
) -> HTMLResponse:
    if not settings.development_routes_enabled:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            context={},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    client = await gateway.get_by_id(client_id)
    if client is None:
        return templates.TemplateResponse(
            request=request,
            name="not_found.html",
            context={},
            status_code=status.HTTP_404_NOT_FOUND,
        )

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"client": client},
    )
