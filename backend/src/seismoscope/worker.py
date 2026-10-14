"""Database-backed MiniSEED acquisition and processing worker."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select, update

from seismoscope.db.models import AnalysisResult, Event, ProcessingJob, Station, Waveform
from seismoscope.db.session import SessionLocal
from seismoscope.services.signals import analyse, download_waveform, save_original
from seismoscope.settings import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


async def claim_job() -> UUID | None:
    async with SessionLocal() as session:
        async with session.begin():
            now = datetime.now(timezone.utc)
            await session.execute(
                update(ProcessingJob)
                .where(
                    ProcessingJob.job_type == "waveform_analysis",
                    ProcessingJob.status == "running",
                    ProcessingJob.locked_at < now - timedelta(minutes=15),
                )
                .values(status="failed", locked_at=None, last_error="Worker stopped before analysis completed")
            )
            job = (await session.execute(select(ProcessingJob).where(ProcessingJob.job_type == "waveform_analysis", ProcessingJob.status == "pending", ProcessingJob.available_at <= now).order_by(ProcessingJob.created_at).with_for_update(skip_locked=True).limit(1))).scalar_one_or_none()
            if not job:
                return None
            job.status = "running"
            job.locked_at = now
            job.attempts += 1
            return job.id


async def execute(job_id: UUID) -> None:
    async with SessionLocal() as session:
        job = await session.get(ProcessingJob, job_id)
        options = job.payload["options"]
        event = await session.get(Event, UUID(job.payload["event_id"]))
        event_id = event.id
        event_time = event.occurred_at
        start = event_time - timedelta(seconds=options["seconds_before"])
        end = event_time + timedelta(seconds=options["seconds_after"])
        completed, failures = [], []
        for station_id in job.payload["station_ids"]:
            station = await session.get(Station, UUID(station_id))
            station_code = f"{station.network_code}.{station.station_code}"
            try:
                raw = await download_waveform(station.network_code, station.station_code, options["channel"], start, end)
                metrics, series, metadata = analyse(raw, options["filter_low_hz"], options["filter_high_hz"], options["normalize"])
                if metrics["estimated_arrival_seconds"] is not None:
                    arrival = metadata["start_time"].replace(tzinfo=timezone.utc) + timedelta(seconds=metrics["estimated_arrival_seconds"])
                    metrics["arrival_from_origin_seconds"] = round((arrival - event_time).total_seconds(), 3)
                key, checksum = save_original(raw, str(event_id), str(station.id))
                waveform = Waveform(event_id=event_id, station_id=station.id, channel_code=metadata["channel"], start_time=metadata["start_time"].replace(tzinfo=timezone.utc), end_time=metadata["end_time"].replace(tzinfo=timezone.utc), sample_rate_hz=metadata["sample_rate_hz"], storage_key=key, checksum_sha256=checksum, source="EarthScope")
                session.add(waveform)
                await session.flush()
                session.add(AnalysisResult(waveform_id=waveform.id, parameters=metadata["parameters"], metrics=metrics, series=series))
                await session.commit()
                completed.append(str(waveform.id))
            except Exception as error:
                await session.rollback()
                logger.warning("station %s failed: %s", station_code, error)
                failures.append(f"{station_code}: {error}")
        job = await session.get(ProcessingJob, job_id)
        job.payload = {**job.payload, "waveform_ids": completed}
        job.status = "succeeded" if completed else "failed"
        job.last_error = "; ".join(failures)[:4000] or None
        job.locked_at = None
        await session.commit()


async def worker_loop() -> None:
    logger.info("analysis worker started")
    while True:
        try:
            job_id = await claim_job()
            if job_id:
                await execute(job_id)
            else:
                await asyncio.sleep(settings.worker_poll_seconds)
        except Exception:
            logger.exception("worker cycle failed")
            await asyncio.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    asyncio.run(worker_loop())
