from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.core.security import csrf_token
from src.web.dependencies import CurrentAdmin
from src.web.routes.pages import templates

router = APIRouter(prefix="/admin", tags=["admin panel"])

SECTIONS = [
    {
        "title": "Партнёры",
        "description": "Список, поиск, блокировка, заметки.",
        "url": "/admin/partners",
    },
    {
        "title": "Суммы override по сети",
        "description": "Фиксированная сумма за 1-3 уровень приглашённых.",
        "url": "/admin/network/rates",
    },
    {
        "title": "Дерево сети",
        "description": "Поиск партнёра и просмотр его сети приглашений.",
        "url": "/admin/network/tree",
    },
    {
        "title": "Заявки",
        "description": "Все заявки от партнёров, статус доставки в Битрикс.",
        "url": "/admin/applications",
    },
    {
        "title": "Выплаты",
        "description": "Календарь выплат, отметка «выплачено», просрочки.",
        "url": "/admin/payouts",
    },
    {
        "title": "Материалы",
        "description": "Вопросы и ответы на странице «Как это работает».",
        "url": "/admin/faq",
    },
]


@router.get("", response_class=HTMLResponse)
async def admin_panel(request: Request, _admin: CurrentAdmin) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="admin_panel.html",
        context={"sections": SECTIONS, "csrf_token": csrf_token(request.session)},
    )
