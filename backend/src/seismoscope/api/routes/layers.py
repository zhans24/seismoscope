from fastapi import APIRouter, HTTPException, status

from seismoscope.services.tectonics import PlateBoundaryClient, TectonicLayerUnavailable

router = APIRouter()


@router.get("/plate-boundaries")
async def plate_boundaries() -> dict:
    try:
        return await PlateBoundaryClient().fetch_boundaries()
    except TectonicLayerUnavailable as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="USGS tectonic layer is temporarily unavailable") from error
