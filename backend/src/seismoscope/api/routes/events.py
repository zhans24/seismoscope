from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, status

from seismoscope.services.earthscope import EarthscopeClient, EarthscopeUnavailable

router = APIRouter()


@router.get("")
async def search_events(
    start: datetime = Query(description="Начало периода в ISO 8601"),
    end: datetime = Query(description="Конец периода в ISO 8601"),
    min_magnitude: float | None = Query(default=None, ge=-2, le=10),
    max_magnitude: float | None = Query(default=None, ge=-2, le=10),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Search public EarthScope catalogue without exposing the provider to the browser."""
    if start >= end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start must be earlier than end")
    try:
        result = await EarthscopeClient().search_events(
            start=start, end=end, min_magnitude=min_magnitude, max_magnitude=max_magnitude, limit=limit
        )
    except EarthscopeUnavailable as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="EarthScope catalogue is temporarily unavailable") from error
    return {"source": result["source"], "count": len(result["items"]), "items": result["items"]}
