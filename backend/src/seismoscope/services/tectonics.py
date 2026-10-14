import httpx


class TectonicLayerUnavailable(RuntimeError):
    pass


class PlateBoundaryClient:
    url = "https://earthquake.usgs.gov/arcgis/rest/services/eq/map_plateboundaries/MapServer/1/query"

    async def fetch_boundaries(self) -> dict:
        params = {"where": "1=1", "outFields": "LABEL,NAME", "returnGeometry": "true", "outSR": "4326", "f": "geojson"}
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.get(self.url, params=params)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TectonicLayerUnavailable(str(error)) from error
        return {"source": "USGS Tectonic Plate Boundaries", "features": data.get("features", [])}
