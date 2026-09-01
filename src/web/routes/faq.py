from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from src.core.config import get_settings
from src.web.dependencies import CurrentAgent
from src.web.routes.pages import templates

router = APIRouter(tags=["faq"])

FAQ_ITEMS = [
    (
        "Когда я получу деньги?",
        "Аванс начисляется, когда клиент подписывает договор. Основная выплата — когда "
        "клиент оплачивает депозит по делу. Статус каждой выплаты видно в вашем кабинете.",
    ),
    (
        "Как зафиксировать клиента за собой?",
        "Клиент закрепляется за вами автоматически, как только переходит по вашей "
        "персональной ссылке и оставляет заявку. Действует правило: кто зафиксировал "
        "клиента первым, тот и получает вознаграждение.",
    ),
    (
        "Что делать если человек уже обращался в Правбюро?",
        "Если по этому клиенту уже есть заявка от другого партнёра или он уже клиент "
        "Правбюро, новая заявка не создаст дубль — вознаграждение получит тот, кто "
        "зафиксировал клиента первым.",
    ),
    (
        "Как сформировать чек самозанятого?",
        "Чек формируется в приложении «Мой налог» на сумму полученной выплаты.",
    ),
    (
        "Как узнать на каком этапе мой клиент?",
        "Текущий статус по каждому клиенту виден в вашем кабинете.",
    ),
]


@router.get("/faq", response_class=HTMLResponse)
async def faq_page(request: Request, agent: CurrentAgent) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="faq.html",
        context={
            "agent": agent,
            "faq_items": FAQ_ITEMS,
            "telegram_manager_url": settings.telegram_manager_url,
            "telegram_materials_url": settings.telegram_materials_url,
        },
    )
