from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import csrf_token, valid_csrf
from src.services.admin_faq import (
    create_faq_item,
    delete_faq_item,
    list_faq_items,
    move_faq_item,
    update_faq_item,
)
from src.web.dependencies import CurrentAdmin
from src.web.routes.pages import templates

router = APIRouter(prefix="/admin/faq", tags=["admin faq"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("", response_class=HTMLResponse)
async def faq_page(request: Request, _admin: CurrentAdmin, session: Session) -> HTMLResponse:
    items = await list_faq_items(session)
    return templates.TemplateResponse(
        request=request,
        name="admin_faq.html",
        context={"items": items, "csrf_token": csrf_token(request.session)},
    )


@router.post("/create")
async def faq_create(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    question: Annotated[str, Form()],
    answer: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf) and question.strip() and answer.strip():
        await create_faq_item(session, question, answer)
    return RedirectResponse("/admin/faq", status_code=303)


@router.post("/{item_id}/update")
async def faq_update(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    item_id: int,
    question: Annotated[str, Form()],
    answer: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf) and question.strip() and answer.strip():
        await update_faq_item(session, item_id, question, answer)
    return RedirectResponse("/admin/faq", status_code=303)


@router.post("/{item_id}/delete")
async def faq_delete(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    item_id: int,
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf):
        await delete_faq_item(session, item_id)
    return RedirectResponse("/admin/faq", status_code=303)


@router.post("/{item_id}/move")
async def faq_move(
    request: Request,
    _admin: CurrentAdmin,
    session: Session,
    item_id: int,
    direction: Annotated[str, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if valid_csrf(request.session, csrf) and direction in ("up", "down"):
        await move_faq_item(session, item_id, direction)
    return RedirectResponse("/admin/faq", status_code=303)
