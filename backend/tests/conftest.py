import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest
from app.projects.astronomy import services


@pytest.fixture
def external_api(monkeypatch):
    """External HTTP fixtures, never used by the application outside tests."""
    services._cache.clear()
    monkeypatch.setattr(services, "_horizons_lock", asyncio.Lock())
    monkeypatch.setenv("NASA_CONTACT", "test@example.invalid")
    monkeypatch.delenv("OPEN_METEO_API_KEY", raising=False)
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path == "/v1/search":
            return httpx.Response(200, json={"results": [{"name": "北京", "latitude": 39.9, "longitude": 116.4, "elevation": 50, "timezone": "Asia/Shanghai", "country": "中国"}]})
        if request.url.path == "/v1/forecast":
            date = request.url.params["start_date"]
            temperature = 68 if request.url.params["temperature_unit"] == "fahrenheit" else 20
            hourly = {"time": [date + "T20:00"], "temperature_2m": [temperature], "cloud_cover": [10], "precipitation_probability": [0], "wind_speed_10m": [5], "visibility": [24000], "is_day": [0]}
            return httpx.Response(200, json={"hourly": hourly, "hourly_units": {"temperature_2m": "°F" if temperature == 68 else "°C"}, "timezone": "Asia/Shanghai", "utc_offset_seconds": 28800})
        if request.url.path == "/api/horizons.api":
            elevation = -25 if request.url.params["COMMAND"] == "'10'" else 35
            result = f"Date__(UT)__HR:MN:SS, , , Azi_(a-app), Elev_(a-app), APmag, S-brt, Illu%,\n$$SOE\n2026-Nov-05 12:00:00, , , 120.5, {elevation}, -2.5, 5.0, 80.0,\n$$EOE"
            return httpx.Response(200, json={"signature": {"version": "1.3"}, "result": result})
        raise AssertionError("Unexpected URL: " + request.url.path)

    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(services, "_client", lambda: httpx.AsyncClient(transport=transport))
    yield calls
    services._cache.clear()


@pytest.fixture
def forecast_date():
    return (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=1)).date().isoformat()
