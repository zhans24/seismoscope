import unittest
from unittest.mock import patch

import httpx

from seismoscope.services.earthscope import CatalogueUnavailable, EventCatalogueClient


class FakeClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _url, params):
        self.calls += 1
        return next(self.responses)


class CatalogueTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def response(status, body=None):
        request = httpx.Request("GET", "https://earthquake.usgs.gov/fdsnws/event/1/query")
        return httpx.Response(status, json=body, request=request) if body is not None else httpx.Response(status, request=request)

    async def test_empty_usgs_response_is_not_retried(self):
        client = FakeClient([self.response(204)])
        with patch("seismoscope.services.earthscope.httpx.AsyncClient", return_value=client):
            result = await EventCatalogueClient()._request_payload("https://example.test", {})
        self.assertEqual(result, {"features": []})
        self.assertEqual(client.calls, 1)

    async def test_bad_request_is_not_retried(self):
        client = FakeClient([self.response(400)])
        with patch("seismoscope.services.earthscope.httpx.AsyncClient", return_value=client):
            with self.assertRaises(CatalogueUnavailable):
                await EventCatalogueClient()._request_payload("https://example.test", {})
        self.assertEqual(client.calls, 1)

    async def test_transient_error_is_retried_once(self):
        client = FakeClient([self.response(503), self.response(200, {"features": []})])
        with patch("seismoscope.services.earthscope.httpx.AsyncClient", return_value=client), patch("seismoscope.services.earthscope.asyncio.sleep"):
            result = await EventCatalogueClient()._request_payload("https://example.test", {})
        self.assertEqual(result, {"features": []})
        self.assertEqual(client.calls, 2)


if __name__ == "__main__":
    unittest.main()
