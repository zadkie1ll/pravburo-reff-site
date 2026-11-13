"""Accept IDs or links to our configured Bitrix portal; never fetch user-supplied URLs."""

import re
from urllib.parse import urlsplit

from src.core.config import get_settings


def portal_origin() -> str:
    portal = urlsplit(get_settings().bitrix_lead_url_template)
    if (
        portal.scheme not in {"http", "https"}
        or not portal.hostname
        or portal.username
        or portal.password
    ):
        raise ValueError("Не настроен адрес портала Битрикс24")
    return f"{portal.scheme}://{portal.netloc}"


def entity_link(kind: str, entity_id: str) -> str:
    if kind not in {"deal", "lead"} or not re.fullmatch(r"[1-9][0-9]{0,63}", entity_id):
        raise ValueError("Некорректный ID Битрикс24")
    return f"{portal_origin()}/crm/{kind}/details/{entity_id}/"


def parse_deal_reference(value: str) -> str:
    value = value.strip()
    if re.fullmatch(r"[0-9]{1,64}", value) and int(value) > 0:
        return str(int(value))
    if len(value) > 1000 or any(character.isspace() for character in value):
        raise ValueError("Укажите ID сделки или ссылку на сделку в Битрикс24")
    try:
        candidate, configured = urlsplit(value), urlsplit(portal_origin())
        match = re.fullmatch(r"/crm/deal/details/([1-9][0-9]{0,63})/?", candidate.path)
        if (
            candidate.scheme != configured.scheme
            or candidate.hostname != configured.hostname
            or (candidate.port or (443 if candidate.scheme == "https" else 80))
            != (configured.port or (443 if configured.scheme == "https" else 80))
            or candidate.username is not None
            or candidate.password is not None
            or match is None
        ):
            raise ValueError("Укажите ссылку на сделку вашего портала Битрикс24")
        return match.group(1)
    except ValueError as exc:
        raise ValueError("Укажите ID сделки или ссылку на сделку вашего портала Битрикс24") from exc
