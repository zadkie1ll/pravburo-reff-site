"""The partner's referral QR image (a plain ``<img>`` needs a real URL; the session authorises it).

The cabinet pages and the public referral form are the JSON API in ``api_cabinet.py`` and
``api_referral.py``.
"""

from io import BytesIO

import qrcode
from fastapi import APIRouter
from fastapi.responses import Response

from src.core.config import get_settings
from src.web.dependencies import CurrentAgent

router = APIRouter(tags=["referrals"])


@router.get("/cabinet/referral-qr.png")
async def referral_qr(agent: CurrentAgent) -> Response:
    url = f"{get_settings().public_base_url}/r/{agent.referral_code}"
    image = qrcode.make(url)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")
