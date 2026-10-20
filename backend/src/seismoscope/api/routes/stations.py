from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Response

from seismoscope.cache import cached_json
from seismoscope.services.stations import StationServiceUnavailable, nearby_stations
from seismoscope.settings import settings

router = APIRouter()


@router.get("/nearby")
async def nearby(
    response: Response,
    latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180),
    at: datetime = Query(), radius_km: int = Query(default=800, ge=10, le=20000),
    limit: int = Query(default=8, ge=1, le=30),
) -> dict:
    parameters = {
        "latitude": latitude, "longitude": longitude, "at": at.isoformat(),
        "radius_km": radius_km, "limit": limit,
    }

    async def fetch() -> list[dict]:
        return await nearby_stations(latitude, longitude, at, radius_km, limit)

    try:
        items, cache_status = await cached_json(
            "stations", parameters, fetch,
            fresh_ttl=settings.station_cache_ttl_seconds, stale_ttl=settings.stale_cache_ttl_seconds,
            stale_if=(StationServiceUnavailable,),
        )
    except StationServiceUnavailable as error:
        raise HTTPException(502, "EarthScope station service unavailable") from error
    response.headers["X-Cache"] = cache_status
    return {"source": "EarthScope FDSN Station", "count": len(items), "items": items}
