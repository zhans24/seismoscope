from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from seismoscope.api.router import api_router
from seismoscope.settings import settings

logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(title="SeismoScope API", version="0.1.0", openapi_url="/api/v1/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(api_router, prefix="/api/v1")


def run() -> None:
    import uvicorn
    uvicorn.run("seismoscope.main:app", host="0.0.0.0", port=8000, reload=True)
