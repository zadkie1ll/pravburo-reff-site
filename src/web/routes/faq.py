from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from pravburo_ref_common.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.services.admin_faq import list_faq_items
from src.web.dependencies import OptionalAgent
from src.web.routes.pages import templates

router = APIRouter(tags=["faq"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request, agent: OptionalAgent, session: Session) -> HTMLResponse:
    settings = get_settings()
    items = await list_faq_items(session)
    return templates.TemplateResponse(
        request=request,
        name="faq.html",
        context={
            "agent": agent,
            "faq_items": [(item.question, item.answer) for item in items],
            "telegram_manager_url": settings.telegram_manager_url,
            "telegram_materials_url": settings.telegram_materials_url,
        },
    )
