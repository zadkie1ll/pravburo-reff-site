"""Admin panel data for the React frontend."""

from fastapi import APIRouter
from pydantic import BaseModel

from src.web.api_dependencies import ApiAdmin

router = APIRouter(prefix="/api/v1/site/admin", tags=["site admin api"])

# Sections of the admin panel. Some (rewards, reward rates, partner levels) live in the
# separate bounty service; nginx routes those paths there.
ADMIN_SECTIONS = [
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
        "title": "Начисления",
        "description": "Одобрение и отклонение начислений партнёрам.",
        "url": "/admin/rewards",
    },
    {
        "title": "Суммы аванса и основной выплаты",
        "description": "Редактирование сумм, которые начисляются за аванс и основную выплату.",
        "url": "/admin/reward-rates",
    },
    {
        "title": "Уровни партнёров",
        "description": "Просмотр и ручная правка уровня партнёра (Старт/Актив/Про/Эксперт).",
        "url": "/admin/partner-levels",
    },
    {
        "title": "Материалы",
        "description": "Вопросы и ответы на странице «Как это работает».",
        "url": "/admin/faq",
    },
]


class AdminSection(BaseModel):
    title: str
    description: str
    url: str


class AdminPanel(BaseModel):
    sections: list[AdminSection]


@router.get("", response_model=AdminPanel)
async def admin_panel(_: ApiAdmin) -> AdminPanel:
    return AdminPanel(sections=[AdminSection(**section) for section in ADMIN_SECTIONS])
