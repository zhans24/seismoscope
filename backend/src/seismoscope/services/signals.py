from __future__ import annotations

import hashlib
import io
import math
from pathlib import Path
from uuid import uuid4

import httpx
import numpy as np
from obspy import read

from seismoscope.settings import settings


class WaveformUnavailable(RuntimeError):
    pass


async def download_waveform(network: str, station: str, channel: str, start, end) -> bytes:
    params = {"net": network, "sta": station, "loc": "*", "cha": channel, "start": start.isoformat(), "end": end.isoformat(), "format": "miniseed", "nodata": 404}
    url = f"{settings.earthscope_base_url}/fdsnws/dataselect/1/query"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(90, connect=15), follow_redirects=True) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            if len(response.content) > 30_000_000:
                raise WaveformUnavailable("waveform exceeds 30 MB limit")
            return response.content
    except httpx.HTTPError as error:
        raise WaveformUnavailable(str(error)) from error


def save_original(data: bytes, event_id: str, station_id: str) -> tuple[str, str]:
    root = Path(settings.waveform_storage_path)
    folder = root / event_id
    folder.mkdir(parents=True, exist_ok=True)
    key = f"{event_id}/{station_id}-{uuid4().hex}.mseed"
    target = root / key
    temporary = target.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(target)
    return key, hashlib.sha256(data).hexdigest()


def analyse(data: bytes, low_hz: float, high_hz: float, normalize: bool) -> tuple[dict, dict, dict]:
    stream = read(io.BytesIO(data), format="MSEED")
    if not stream:
        raise WaveformUnavailable("empty MiniSEED stream")
    trace = max(stream, key=lambda item: item.stats.npts)
    if trace.stats.npts < 20:
        raise WaveformUnavailable("waveform is too short")
    sample_rate = float(trace.stats.sampling_rate)
    if high_hz >= sample_rate / 2:
        raise WaveformUnavailable(f"filter high cutoff must be below Nyquist frequency ({sample_rate / 2:.2f} Hz)")
    trace = trace.copy()
    trace.detrend("demean")
    trace.detrend("linear")
    trace.taper(max_percentage=0.05)
    trace.filter("bandpass", freqmin=low_hz, freqmax=high_hz, corners=4, zerophase=True)
    values = np.asarray(trace.data, dtype=np.float64)
    peak = float(np.max(np.abs(values)))
    rms = float(np.sqrt(np.mean(values ** 2)))
    baseline = values[:max(10, len(values) // 10)]
    noise_rms = float(np.sqrt(np.mean(baseline ** 2)))
    snr = round(20 * math.log10(rms / noise_rms), 2) if noise_rms > 0 else None
    threshold = max(noise_rms * 5, peak * 0.12)
    indices = np.flatnonzero(np.abs(values) >= threshold)
    arrival_seconds = round(float(indices[0]) / sample_rate, 3) if len(indices) else None
    display = values / peak if normalize and peak else values
    stride = max(1, math.ceil(len(display) / 1200))
    metrics = {"peak_amplitude_counts": round(peak, 4), "rms_counts": round(rms, 4), "noise_rms_counts": round(noise_rms, 4), "snr_db": snr, "estimated_arrival_seconds": arrival_seconds, "duration_seconds": round(len(values) / sample_rate, 2), "sample_count": len(values)}
    series = {"step_seconds": stride / sample_rate, "values": [round(float(value), 5) for value in display[::stride]], "normalized": normalize}
    parameters = {"detrend": "demean+linear", "taper": 0.05, "filter": "bandpass", "low_hz": low_hz, "high_hz": high_hz, "normalize": normalize, "arrival_method": "threshold (5x noise RMS or 12% peak)"}
    return metrics, series, {"parameters": parameters, "sample_rate_hz": sample_rate, "start_time": trace.stats.starttime.datetime, "end_time": trace.stats.endtime.datetime, "channel": trace.stats.channel}
