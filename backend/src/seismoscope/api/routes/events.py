from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query, Response, status

from seismoscope.cache import cached_json
from seismoscope.services.earthscope import CatalogueUnavailable, EventCatalogueClient
from seismoscope.settings import settings

router = APIRouter()


@router.get("")
async def search_events(
    response: Response,
    start: datetime = Query(description="Начало периода в ISO 8601"),
    end: datetime = Query(description="Конец периода в ISO 8601"),
    min_magnitude: float | None = Query(default=None, ge=-2, le=10),
    max_magnitude: float | None = Query(default=None, ge=-2, le=10),
    min_latitude: float | None = Query(default=None, ge=-90, le=90),
    max_latitude: float | None = Query(default=None, ge=-90, le=90),
    min_longitude: float | None = Query(default=None, ge=-180, le=180),
    max_longitude: float | None = Query(default=None, ge=-180, le=180),
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Search the USGS event catalogue through the backend."""
    if start >= end:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start must be earlier than end")
    if (min_latitude is None) != (max_latitude is None) or (min_longitude is None) != (max_longitude is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="all country bounds must be provided together")
    parameters = {
        "start": start.isoformat(), "end": end.isoformat(), "min_magnitude": min_magnitude,
        "max_magnitude": max_magnitude, "limit": limit, "min_latitude": min_latitude,
        "max_latitude": max_latitude, "min_longitude": min_longitude, "max_longitude": max_longitude,
    }

    async def fetch() -> dict:
        return await EventCatalogueClient().search_events(
            start=start, end=end, min_magnitude=min_magnitude, max_magnitude=max_magnitude, limit=limit,
            min_latitude=min_latitude, max_latitude=max_latitude, min_longitude=min_longitude, max_longitude=max_longitude,
        )

    normalized_end = end if end.tzinfo else end.replace(tzinfo=timezone.utc)
    is_historical = normalized_end < datetime.now(timezone.utc) - timedelta(days=1)
    fresh_ttl = settings.historical_event_cache_ttl_seconds if is_historical else settings.event_cache_ttl_seconds
    try:
        result, cache_status = await cached_json(
            "events", parameters, fetch, fresh_ttl=fresh_ttl, stale_ttl=settings.stale_cache_ttl_seconds,
            stale_if=(CatalogueUnavailable,),
        )
    except CatalogueUnavailable as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="USGS catalogue is temporarily unavailable") from error
    response.headers["X-Cache"] = cache_status
    return {"source": result["source"], "count": len(result["items"]), "items": result["items"]}
