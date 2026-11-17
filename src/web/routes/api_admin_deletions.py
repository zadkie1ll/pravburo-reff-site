"""Explicit preview and confirmation of local admin deletions."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pravburo_ref_common.database import get_session
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.admin_deletion import Kind, delete_record, deletion_plan
from src.web.api_dependencies import ApiAdmin, CsrfProtected
from src.web.api_errors import ApiError
from src.web.api_schemas import OkResponse

router = APIRouter(prefix="/api/v1/site/admin/deletions", tags=["site admin api"])
Session = Annotated[AsyncSession, Depends(get_session)]


class DeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(pattern=r"^[0-9a-f]{64}$")


@router.get("/{kind}/{target_id}")
async def preview(_: ApiAdmin, session: Session, kind: Kind, target_id: int):
    try:
        return (await deletion_plan(session, kind, target_id)).preview()
    except LookupError as exc:
        raise ApiError(404, "not_found", str(exc)) from exc


@router.delete("/{kind}/{target_id}", dependencies=[CsrfProtected], response_model=OkResponse)
async def remove(
    admin: ApiAdmin, session: Session, kind: Kind, target_id: int, body: DeleteRequest
):
    try:
        await delete_record(session, kind, target_id, body.token, admin.id)
    except LookupError as exc:
        raise ApiError(404, "not_found", str(exc)) from exc
    except ValueError as exc:
        raise ApiError(409, "cannot_delete", str(exc)) from exc
    except DBAPIError as exc:
        await session.rollback()
        if getattr(exc.orig, "sqlstate", None) in {"23503", "40001", "40P01"}:
            raise ApiError(
                409,
                "deletion_conflict",
                "Связанные данные изменились. Обновите подтверждение удаления",
            ) from exc
        raise
    return OkResponse()
