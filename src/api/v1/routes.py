from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import LegacyGatewayDependency
from src.api.v1.schemas import LegacyClientResponse

router = APIRouter(prefix="/api/v1", tags=["legacy clients"])


@router.get("/legacy-clients/{client_id}", response_model=LegacyClientResponse)
async def get_legacy_client(
    client_id: int,
    gateway: LegacyGatewayDependency,
) -> LegacyClientResponse:
    client = await gateway.get_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")
    return LegacyClientResponse.from_record(client)
