from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from seismoscope.db.models import AnalysisResult, Event, ProcessingJob, Station, Waveform
from seismoscope.db.session import get_session

router = APIRouter()


class EventInput(BaseModel):
    id: str = Field(min_length=1, max_length=255)
    time: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    magnitude: float | None = None
    depth_km: float | None = None
    place: str = ""


class StationInput(BaseModel):
    network: str = Field(pattern=r"^[A-Za-z0-9]{1,8}$")
    station: str = Field(pattern=r"^[A-Za-z0-9]{1,8}$")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    elevation_m: float | None = None


class AnalysisInput(BaseModel):
    event: EventInput
    stations: list[StationInput] = Field(min_length=1, max_length=5)
    channel: str = Field(default="BHZ", pattern=r"^[A-Z0-9?*]{3}$")
    seconds_before: int = Field(default=60, ge=10, le=600)
    seconds_after: int = Field(default=300, ge=30, le=1800)
    filter_low_hz: float = Field(default=0.5, gt=0, le=20)
    filter_high_hz: float = Field(default=8.0, gt=0, le=40)
    normalize: bool = False

    @model_validator(mode="after")
    def validate_filter(self):
        if self.filter_low_hz >= self.filter_high_hz:
            raise ValueError("filter_low_hz must be less than filter_high_hz")
        if len({(s.network, s.station) for s in self.stations}) != len(self.stations):
            raise ValueError("stations must be unique")
        return self


@router.post("", status_code=202)
async def create_analysis(body: AnalysisInput, session: AsyncSession = Depends(get_session)) -> dict:
    event = (await session.execute(select(Event).where(Event.source == "USGS", Event.source_event_id == body.event.id))).scalar_one_or_none()
    if event is None:
        event = Event(source="USGS", source_event_id=body.event.id, occurred_at=body.event.time, latitude=body.event.latitude, longitude=body.event.longitude, magnitude=body.event.magnitude, depth_km=body.event.depth_km, place=body.event.place, raw_payload=body.event.model_dump(mode="json"))
        session.add(event)
        await session.flush()
    station_ids = []
    for item in body.stations:
        station = (await session.execute(select(Station).where(Station.network_code == item.network, Station.station_code == item.station))).scalar_one_or_none()
        if station is None:
            station = Station(network_code=item.network, station_code=item.station, latitude=item.latitude, longitude=item.longitude, elevation_m=item.elevation_m, station_metadata={})
            session.add(station)
            await session.flush()
        station_ids.append(str(station.id))
    job = ProcessingJob(job_type="waveform_analysis", status="pending", payload={"event_id": str(event.id), "station_ids": station_ids, "options": body.model_dump(mode="json")}, attempts=0)
    session.add(job)
    await session.commit()
    return {"id": str(job.id), "status": job.status}


@router.get("/{job_id}")
async def get_analysis(job_id: UUID, session: AsyncSession = Depends(get_session)) -> dict:
    job = await session.get(ProcessingJob, job_id)
    if job is None or job.job_type != "waveform_analysis":
        raise HTTPException(404, "Analysis not found")
    waveform_ids = [UUID(value) for value in job.payload.get("waveform_ids", [])]
    traces = []
    if waveform_ids:
        rows = (await session.execute(select(Waveform, Station, AnalysisResult).join(Station, Waveform.station_id == Station.id).join(AnalysisResult, AnalysisResult.waveform_id == Waveform.id).where(Waveform.id.in_(waveform_ids)))).all()
        for waveform, station, result in rows:
            traces.append({"station": f"{station.network_code}.{station.station_code}", "latitude": station.latitude, "longitude": station.longitude, "channel": waveform.channel_code, "sample_rate_hz": waveform.sample_rate_hz, "start_time": waveform.start_time.isoformat(), "metrics": result.metrics, "series": result.series, "checksum_sha256": waveform.checksum_sha256})
    return {"id": str(job.id), "status": job.status, "attempts": job.attempts, "error": job.last_error, "event_id": job.payload.get("event_id"), "options": job.payload.get("options"), "station_results": job.payload.get("station_results", []), "traces": traces}
