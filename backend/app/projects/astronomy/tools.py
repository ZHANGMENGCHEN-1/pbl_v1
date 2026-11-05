from langchain.tools import tool
from . import services


def build_tools(config):
    @tool
    async def weather(location: str, date: str) -> dict:
        """Get real Open-Meteo hourly forecast for a city or 'latitude,longitude' and YYYY-MM-DD date. Forecast dates only, up to 16 days. Ask for country/region or coordinates when a city is ambiguous. Match local hourly time to the requested observing time."""
        return await services.weather_forecast(location, date, config.weather.units)

    @tool
    async def astronomy(location: str, time: str) -> dict:
        """Get real NASA/JPL Horizons Moon, Jupiter, Saturn and Sun ephemerides for a city or 'latitude,longitude' and ISO datetime WITH UTC offset (e.g. 2026-11-05T20:00:00+08:00). Returns azimuth, elevation, magnitude and illumination when available. Above horizon does not guarantee visibility. No stars/deep-sky catalog. Ask for missing timezone."""
        return await services.astronomy_ephemeris(location, time, config.astronomy.equipment)

    result = [t for t, enabled in [(weather, config.weather.enabled), (astronomy, config.astronomy.enabled)] if enabled]
    for item in result:
        item.handle_tool_error = True
    return result
