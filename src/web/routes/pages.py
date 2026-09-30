from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter(tags=["web"])


@router.get("/sw.js", include_in_schema=False)
async def service_worker() -> FileResponse:
    # Served at root (not under /static) so its default registration scope
    # covers the whole origin, not just /static/*.
    static_dir = Path(__file__).parents[1] / "static"
    return FileResponse(static_dir / "sw.js", media_type="application/javascript")
