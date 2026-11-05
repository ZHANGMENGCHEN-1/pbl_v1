"""Opt-in live tools test. No LLM calls. Configure NASA_CONTACT for Horizons."""
import argparse
import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.main import app  # Loads .env without exposing keys.
from app.projects.astronomy import services
from langchain_core.tools import ToolException


async def main(args):
    tomorrow = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=1)).date().isoformat()
    try:
        weather = await services.weather_forecast(args.location, tomorrow, "celsius")
        print(json.dumps({"source": weather["source"], "date": tomorrow, "hours": len(weather["hourly"]), "timezone": weather["timezone"]}, ensure_ascii=False))
        if not args.weather_only:
            sky = await services.astronomy_ephemeris(args.location, tomorrow + "T20:00:00+08:00", "binoculars")
            print(json.dumps({"source": sky["source"], "time_utc": sky["time_utc"], "targets": sky["targets"], "sun_elevation_deg": sky["sun_elevation_deg"]}, ensure_ascii=False))
    except ToolException as exc:
        print(str(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--location", default="39.9,116.4", help="city or latitude,longitude")
    parser.add_argument("--weather-only", action="store_true")
    asyncio.run(main(parser.parse_args()))
