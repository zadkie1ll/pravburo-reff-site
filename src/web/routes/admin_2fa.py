"""The QR image of the admin's 2FA setup.

The rest of the 2FA step is the JSON API in ``api_admin_2fa.py``; the React setup page shows this
image with a plain ``<img>``, which needs a real URL (the session cookie authorises it).
"""

from io import BytesIO
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pravburo_ref_common.database import get_session
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.auth import get_or_create_totp_secret
from src.core.totp import provisioning_uri
from src.web.dependencies import PendingAdmin

router = APIRouter(prefix="/admin/2fa", tags=["admin 2fa"])
Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/qr.png")
async def setup_qr(admin: PendingAdmin, session: Session) -> Response:
    secret = await get_or_create_totp_secret(session, admin)
    uri = provisioning_uri(secret, admin.email or f"agent-{admin.id}")
    image = qrcode.make(uri)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return Response(buffer.getvalue(), media_type="image/png")
