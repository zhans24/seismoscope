from __future__ import annotations

from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

import httpx

from seismoscope.settings import settings


class StationServiceUnavailable(RuntimeError):
    pass


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    a = sin(radians(lat2 - lat1) / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * asin(min(1.0, sqrt(a)))


async def nearby_stations(latitude: float, longitude: float, at: datetime, radius_km: int, limit: int) -> list[dict]:
    params = {
        "latitude": latitude, "longitude": longitude,
        "maxradius": min(radius_km / 111.2, 180),
        "starttime": at.isoformat(), "endtime": (at + timedelta(seconds=1)).isoformat(),
        "channel": "BHZ", "level": "station", "format": "text", "nodata": 404,
    }
    url = f"{settings.earthscope_base_url}/fdsnws/station/1/query"
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            response = await client.get(url, params=params)
            if response.status_code == 404:
                return []
            response.raise_for_status()
            lines = response.text.splitlines()
    except httpx.HTTPError as error:
        raise StationServiceUnavailable(str(error)) from error
    stations = []
    for line in lines:
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if len(fields) < 6:
            continue
        try:
            lat, lon = float(fields[2]), float(fields[3])
            stations.append({
                "network": fields[0], "station": fields[1], "latitude": lat,
                "longitude": lon, "elevation_m": float(fields[4]),
                "site_name": fields[5], "distance_km": round(distance_km(latitude, longitude, lat, lon), 1),
            })
        except ValueError:
            continue
    return sorted(stations, key=lambda item: item["distance_km"])[:limit]
