"""JSON API for the React frontend. Thin layer over the same services the HTML routes use."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pravburo_ref_common.database import get_session
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.security import csrf_token
from src.services.admin_faq import list_faq_items
from src.web.api_dependencies import onboarding_required
from src.web.dependencies import OptionalAgent

router = APIRouter(prefix="/api/v1/site", tags=["site api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class SessionInfo(BaseModel):
    authenticated: bool
    email: str | None
    role: Literal["admin", "agent"] | None
    onboarding_required: bool
    csrf_token: str


class FaqItem(BaseModel):
    question: str
    answer: str


class FaqResponse(BaseModel):
    items: list[FaqItem]
    telegram_manager_url: str
    telegram_materials_url: str


@router.get("/me", response_model=SessionInfo)
async def me(request: Request, agent: OptionalAgent) -> SessionInfo:
    return SessionInfo(
        authenticated=agent is not None,
        email=agent.email if agent is not None else None,
        role=agent.role.value if agent is not None else None,
        onboarding_required=agent is not None and onboarding_required(agent),
        csrf_token=csrf_token(request.session),
    )


@router.get("/faq", response_model=FaqResponse)
async def faq(session: Session) -> FaqResponse:
    settings = get_settings()
    items = await list_faq_items(session)
    return FaqResponse(
        items=[FaqItem(question=item.question, answer=item.answer) for item in items],
        telegram_manager_url=settings.telegram_manager_url,
        telegram_materials_url=settings.telegram_materials_url,
    )
