import asyncio
import httpx
import pytest
from langchain_core.tools import ToolException
from app.projects.astronomy import services


def run(coro):
    return asyncio.run(coro)


def test_astronomy_coordinates_time_and_cache(external_api, forecast_date):
    value = run(services.astronomy_ephemeris("39.9,116.4", forecast_date + "T20:00:00+08:00", "binoculars"))
    assert value["time_utc"].endswith("12:00:00+00:00")
    assert [t["name"] for t in value["targets"]] == ["月球", "木星", "土星"]
    assert value["sun_elevation_deg"] == -25
    assert value["targets"][0]["azimuth_deg"] == 120.5
    assert len(external_api) == 4
    assert external_api[0].url.params["SITE_COORD"] == "'116.4,39.9,0.0'"
    assert "test@example.invalid" in external_api[0].headers["User-Agent"]
    run(services.astronomy_ephemeris("39.9,116.4", forecast_date + "T20:00:00+08:00", "naked_eye"))
    assert len(external_api) == 4


def test_naive_time_and_contact_required(monkeypatch):
    with pytest.raises(ToolException, match="时区"):
        run(services.astronomy_ephemeris("北京", "2026-11-05T20:00:00", "binoculars"))
    monkeypatch.delenv("NASA_CONTACT", raising=False)
    with pytest.raises(ToolException, match="NASA_CONTACT"):
        run(services.astronomy_ephemeris("北京", "2026-11-05T20:00:00+08:00", "binoculars"))


def test_weather_outside_forecast_and_bad_coordinates(external_api):
    with pytest.raises(ToolException, match="16 天"):
        run(services.weather_forecast("北京", "2000-01-01", "celsius"))
    with pytest.raises(ToolException, match="纬度"):
        run(services.resolve_location("91,0"))


@pytest.mark.parametrize("version", ["1.2", "1.3"])
def test_horizons_unknown_version_missing_data_and_no_fabrication(version):
    with pytest.raises(ToolException, match="版本"):
        services.parse_horizons({"signature": {"version": "9"}})
    with pytest.raises(ToolException, match="未返回星历"):
        services.parse_horizons({"signature": {"version": "1.3"}, "error": "bad request"})
    data = {"signature": {"version": version}, "result": "Date__(UT)__HR:MN:SC.fff, , , Azi_(a-app), Elev_(a-app), APmag, Illu%,\n$$SOE\n2026-Nov-05 12:00:00.000, , , 30, -12, n.a., n.a.,\n$$EOE"}
    value = services.parse_horizons(data)
    assert value["above_horizon"] is False
    assert value["apparent_magnitude"] is None
    assert value["illuminated_percent"] is None


def test_upstream_error_never_leaks_key(monkeypatch):
    transport = httpx.MockTransport(lambda request: httpx.Response(429, json={"error": "secret"}))
    monkeypatch.setattr(services, "_client", lambda: httpx.AsyncClient(transport=transport))
    with pytest.raises(ToolException) as error:
        run(services.request_json("https://api.example/test", {"apikey": "secret"}, "Test"))
    assert "429" in str(error.value)
    assert "secret" not in str(error.value)


def test_ambiguous_place_and_missing_place(monkeypatch):
    services._cache.clear()
    payload = {"results": [{"name": "Paris", "admin1": "A", "country": "X"}, {"name": "Paris", "admin1": "B", "country": "Y"}]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
    monkeypatch.setattr(services, "_client", lambda: httpx.AsyncClient(transport=transport))
    with pytest.raises(ToolException, match="歧义"):
        run(services.resolve_location("Paris"))
    payload.clear()
    with pytest.raises(ToolException, match="未找到"):
        run(services.resolve_location("nowhere"))
