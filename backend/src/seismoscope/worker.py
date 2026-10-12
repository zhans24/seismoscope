"""Durable worker entry point. Job execution is added as import/analysis services are implemented."""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

from seismoscope.db.session import SessionLocal
from seismoscope.settings import settings

logger = logging.getLogger(__name__)


async def worker_loop() -> None:
    logger.info("worker started")
    while True:
        # A database-backed queue survives restarts and makes retries auditable.
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        await asyncio.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(worker_loop())
