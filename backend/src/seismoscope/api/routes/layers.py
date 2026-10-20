from fastapi import APIRouter, HTTPException, Response, status

from seismoscope.cache import cached_json
from seismoscope.services.tectonics import PlateBoundaryClient, TectonicLayerUnavailable
from seismoscope.settings import settings

router = APIRouter()


@router.get("/plate-boundaries")
async def plate_boundaries(response: Response) -> dict:
    try:
        result, cache_status = await cached_json(
            "plate-boundaries", {}, PlateBoundaryClient().fetch_boundaries,
            fresh_ttl=settings.plate_cache_ttl_seconds, stale_ttl=settings.stale_cache_ttl_seconds,
            stale_if=(TectonicLayerUnavailable,),
        )
    except TectonicLayerUnavailable as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="USGS tectonic layer is temporarily unavailable") from error
    response.headers["X-Cache"] = cache_status
    return result
