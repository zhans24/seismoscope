from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import httpx

from seismoscope.settings import settings


class CatalogueUnavailable(RuntimeError):
    pass


class EventCatalogueClient:
    """Boundary around the selected global event catalogue."""

    _RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

    async def search_events(
        self,
        *,
        start: datetime,
        end: datetime,
        min_magnitude: float | None,
        max_magnitude: float | None,
        limit: int,
        min_latitude: float | None,
        max_latitude: float | None,
        min_longitude: float | None,
        max_longitude: float | None,
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
        if min_latitude is not None:
            params.update({"minlatitude": min_latitude, "maxlatitude": max_latitude, "minlongitude": min_longitude, "maxlongitude": max_longitude})

        url = f"{settings.usgs_event_base_url}/fdsnws/event/1/query"
        payload = await self._request_payload(url, params)

        return {"source": "USGS FDSN Event API", "items": [self._to_event(feature) for feature in payload.get("features", [])]}

    async def _request_payload(self, url: str, params: dict[str, str | int | float]) -> dict:
        """Fetch the public catalogue, retrying only transient upstream failures."""
        error: Exception | None = None
        headers = {"User-Agent": "SeismoScope/0.1 (seismic catalogue research application)"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), follow_redirects=True, headers=headers) as client:
            for attempt in range(3):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code in self._RETRYABLE_STATUS_CODES:
                        error = httpx.HTTPStatusError(
                            f"USGS returned HTTP {response.status_code}", request=response.request, response=response
                        )
                    else:
                        response.raise_for_status()
                        payload = response.json()
                        if not isinstance(payload, dict):
                            raise ValueError("USGS returned an unexpected response")
                        return payload
                except (httpx.HTTPError, ValueError) as caught:
                    error = caught

                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise CatalogueUnavailable(str(error or "USGS catalogue request failed")) from error

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
