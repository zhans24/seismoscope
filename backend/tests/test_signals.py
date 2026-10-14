import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx

from seismoscope.services.signals import WaveformNotFound, WaveformUnavailable, download_waveform


class FakeClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, _url, params):
        return self.response


class DownloadWaveformTests(unittest.IsolatedAsyncioTestCase):
    async def request(self, status, content=b""):
        response = httpx.Response(status, content=content, request=httpx.Request("GET", "https://service.earthscope.org"))
        start = datetime(2026, 10, 14, 10, 48, tzinfo=timezone.utc)
        with patch("seismoscope.services.signals.httpx.AsyncClient", return_value=FakeClient(response)):
            return await download_waveform("YC", "TNG2", "BHZ", start, start + timedelta(minutes=6))

    async def test_missing_samples_are_not_a_service_error(self):
        with self.assertRaises(WaveformNotFound) as caught:
            await self.request(404)
        self.assertNotIn("https://", str(caught.exception))

    async def test_empty_success_is_also_missing_samples(self):
        with self.assertRaises(WaveformNotFound):
            await self.request(204)

    async def test_service_error_is_distinct_from_missing_samples(self):
        with self.assertRaises(WaveformUnavailable) as caught:
            await self.request(503)
        self.assertNotIsInstance(caught.exception, WaveformNotFound)
        self.assertEqual(str(caught.exception), "EarthScope вернул HTTP 503")

    async def test_available_samples_are_returned(self):
        self.assertEqual(await self.request(200, b"miniSEED"), b"miniSEED")


if __name__ == "__main__":
    unittest.main()
