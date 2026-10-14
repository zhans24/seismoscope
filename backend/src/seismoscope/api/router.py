from fastapi import APIRouter

from seismoscope.api.routes.health import router as health_router
from seismoscope.api.routes.events import router as events_router
from seismoscope.api.routes.layers import router as layers_router
from seismoscope.api.routes.analysis import router as analysis_router
from seismoscope.api.routes.stations import router as stations_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(events_router, prefix="/events", tags=["events"])
api_router.include_router(layers_router, prefix="/layers", tags=["map layers"])
api_router.include_router(stations_router, prefix="/stations", tags=["stations"])
api_router.include_router(analysis_router, prefix="/analyses", tags=["analyses"])
