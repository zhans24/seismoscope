from fastapi import APIRouter

from seismoscope.api.routes.health import router as health_router
from seismoscope.api.routes.events import router as events_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(events_router, prefix="/events", tags=["events"])
