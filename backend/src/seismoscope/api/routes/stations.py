from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from seismoscope.services.stations import StationServiceUnavailable, nearby_stations

router = APIRouter()


@router.get("/nearby")
async def nearby(
    latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180),
    at: datetime = Query(), radius_km: int = Query(default=800, ge=10, le=20000),
    limit: int = Query(default=8, ge=1, le=30),
) -> dict:
    try:
        items = await nearby_stations(latitude, longitude, at, radius_km, limit)
    except StationServiceUnavailable as error:
        raise HTTPException(502, "EarthScope station service unavailable") from error
    return {"source": "EarthScope FDSN Station", "count": len(items), "items": items}
