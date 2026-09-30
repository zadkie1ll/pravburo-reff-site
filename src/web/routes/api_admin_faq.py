"""Admin: the editable FAQ ("Материалы") that partners see on /faq."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import FaqItem
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin_faq import (
    create_faq_item,
    delete_faq_item,
    list_faq_items,
    move_faq_item,
    update_faq_item,
)
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.api_schemas import OkResponse

router = APIRouter(prefix="/api/v1/site/admin/faq", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]

QUESTION_MAX = 300  # the column is String(300)
ANSWER_MAX = 10_000


class FaqItemOut(BaseModel):
    id: int
    question: str
    answer: str


class FaqList(BaseModel):
    items: list[FaqItemOut]


class FaqInput(BaseModel):
    question: str = Field(max_length=QUESTION_MAX)
    answer: str = Field(max_length=ANSWER_MAX)


class MoveRequest(BaseModel):
    direction: Literal["up", "down"]


def _checked(body: FaqInput) -> None:
    """Both parts are required; blanks are refused (the old form silently ignored them)."""
    fields = {
        name: "required"
        for name, value in (("question", body.question), ("answer", body.answer))
        if not value.strip()
    }
    if fields:
        raise ApiError(400, "validation_error", "Заполните вопрос и ответ", fields)


async def _existing(session: AsyncSession, item_id: int) -> None:
    if await session.get(FaqItem, item_id) is None:
        raise ApiError(404, "not_found", "Вопрос не найден")


@router.get("", response_model=FaqList)
async def faq(_: ApiAdmin, session: Session) -> FaqList:
    items = await list_faq_items(session)
    return FaqList(
        items=[FaqItemOut(id=item.id, question=item.question, answer=item.answer) for item in items]
    )


@router.post("", response_model=OkResponse, dependencies=[CsrfProtected])
async def create(_: ApiAdmin, session: Session, body: FaqInput) -> OkResponse:
    _checked(body)
    await create_faq_item(session, body.question, body.answer)
    return OkResponse()


@router.put("/{item_id}", response_model=OkResponse, dependencies=[CsrfProtected])
async def update(_: ApiAdmin, session: Session, item_id: int, body: FaqInput) -> OkResponse:
    _checked(body)
    await _existing(session, item_id)
    await update_faq_item(session, item_id, body.question, body.answer)
    return OkResponse()


@router.delete("/{item_id}", response_model=OkResponse, dependencies=[CsrfProtected])
async def delete(_: ApiAdmin, session: Session, item_id: int) -> OkResponse:
    await _existing(session, item_id)
    await delete_faq_item(session, item_id)
    return OkResponse()


@router.post("/{item_id}/move", response_model=OkResponse, dependencies=[CsrfProtected])
async def move(_: ApiAdmin, session: Session, item_id: int, body: MoveRequest) -> OkResponse:
    await _existing(session, item_id)
    await move_faq_item(session, item_id, body.direction)
    return OkResponse()
