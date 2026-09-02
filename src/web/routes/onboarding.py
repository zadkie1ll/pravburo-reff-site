from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pravburo_ref_common.database import get_session
from pravburo_ref_common.models import EmploymentFormat
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import csrf_token, valid_csrf
from src.services.onboarding import EMPLOYMENT_FORMAT_NOTES, save_basic_info, save_payout_info
from src.services.profile import EMPLOYMENT_FORMAT_LABELS
from src.web.dependencies import CurrentAgent
from src.web.routes.pages import templates

router = APIRouter(tags=["onboarding"])
Session = Annotated[AsyncSession, Depends(get_session)]

def _basic_context(request: Request, *, display_name: str = "", error: str = "") -> dict:
    return {
        "csrf_token": csrf_token(request.session),
        "display_name": display_name,
        "employment_formats": EMPLOYMENT_FORMAT_LABELS,
        "employment_format_notes": EMPLOYMENT_FORMAT_NOTES,
        "error": error,
    }


@router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_basic(request: Request, agent: CurrentAgent) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="onboarding_basic.html",
        context=_basic_context(request, display_name=agent.display_name),
    )


@router.post("/onboarding")
async def onboarding_basic_submit(
    request: Request,
    agent: CurrentAgent,
    session: Session,
    display_name: Annotated[str, Form(max_length=200)],
    employment_format: Annotated[EmploymentFormat, Form()],
    csrf: Annotated[str, Form()] = "",
):
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="onboarding_basic.html",
            context=_basic_context(request, display_name=display_name, error="Обновите страницу"),
            status_code=400,
        )
    if not display_name.strip():
        return templates.TemplateResponse(
            request=request,
            name="onboarding_basic.html",
            context=_basic_context(request, display_name=display_name, error="Укажите ФИО"),
            status_code=400,
        )
    await save_basic_info(session, agent, display_name, employment_format)
    return RedirectResponse("/onboarding/payout", status_code=303)


@router.get("/onboarding/payout", response_class=HTMLResponse)
async def onboarding_payout(request: Request, agent: CurrentAgent) -> HTMLResponse:
    if agent.employment_format is None:
        return RedirectResponse("/onboarding", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="onboarding_payout.html",
        context={"csrf_token": csrf_token(request.session), "error": ""},
    )


@router.post("/onboarding/payout")
async def onboarding_payout_submit(
    request: Request,
    agent: CurrentAgent,
    session: Session,
    payout_details: Annotated[str, Form(max_length=200)] = "",
    inn: Annotated[str, Form(max_length=12)] = "",
    csrf: Annotated[str, Form()] = "",
):
    if agent.employment_format is None:
        return RedirectResponse("/onboarding", status_code=303)
    if not valid_csrf(request.session, csrf):
        return templates.TemplateResponse(
            request=request,
            name="onboarding_payout.html",
            context={"csrf_token": csrf_token(request.session), "error": "Обновите страницу"},
            status_code=400,
        )
    try:
        await save_payout_info(session, agent, payout_details, inn)
    except ValueError as exc:
        return templates.TemplateResponse(
            request=request,
            name="onboarding_payout.html",
            context={"csrf_token": csrf_token(request.session), "error": str(exc)},
            status_code=400,
        )
    return RedirectResponse("/cabinet", status_code=303)
