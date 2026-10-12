from __future__ import annotations

from datetime import datetime, timezone

import httpx

from seismoscope.settings import settings


class EarthscopeUnavailable(RuntimeError):
    pass


class EarthscopeClient:
    """Small boundary around the upstream catalogue; retries stay server-side."""

    async def search_events(
        self,
        *,
        start: datetime,
        end: datetime,
        min_magnitude: float | None,
        max_magnitude: float | None,
        limit: int,
    ) -> dict:
        params: dict[str, str | int | float] = {
            "format": "geojson",
            "starttime": start.isoformat(),
            "endtime": end.isoformat(),
            "limit": limit,
            "orderby": "time",
        }
        if min_magnitude is not None:
            params["minmagnitude"] = min_magnitude
        if max_magnitude is not None:
            params["maxmagnitude"] = max_magnitude

        earthscope_url = f"{settings.earthscope_base_url}/fdsnws/event/1/query"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True) as client:
                response = await client.get(earthscope_url, params=params)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise EarthscopeUnavailable(str(error)) from error

        return {"source": "EarthScope FDSN", "items": [self._to_event(feature) for feature in payload.get("features", [])]}

    @staticmethod
    def _to_event(feature: dict) -> dict:
        properties = feature.get("properties", {})
        coordinates = feature.get("geometry", {}).get("coordinates", [None, None, None])
        return {
            "id": feature.get("id"),
            "time": datetime.fromtimestamp(properties["time"] / 1000, tz=timezone.utc).isoformat(),
            "place": properties.get("place") or "Не указано",
            "magnitude": properties.get("mag"),
            "magnitude_type": properties.get("magType"),
            "depth_km": coordinates[2] if len(coordinates) > 2 else None,
            "longitude": coordinates[0],
            "latitude": coordinates[1],
            "detail_url": properties.get("detail"),
        }
