"""External data adapters. Fail explicitly; never substitute simulated data."""
import asyncio
import csv
import math
import os
import re
import time as clock
from collections import OrderedDict
from datetime import date as Date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import httpx
from langchain_core.tools import ToolException

_cache = OrderedDict()
_horizons_lock = asyncio.Lock()
TARGETS = [("301", "月球"), ("599", "木星"), ("699", "土星"), ("10", "太阳")]


def _client():
    return httpx.AsyncClient(timeout=float(os.getenv("TOOL_TIMEOUT_SECONDS", "25")), follow_redirects=False)


async def request_json(url, params, source, headers=None):
    try:
        async with _client() as client:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json()
        if not isinstance(result, dict):
            raise ValueError()
        return result
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        hint = "请求过于频繁，请稍后重试" if code == 429 else "请检查查询范围、服务状态或 API 配置"
        raise ToolException(f"{source} 请求失败（HTTP {code}），{hint}。未生成替代数据。") from None
    except (httpx.HTTPError, ValueError):
        # Never echo URLs or headers: commercial requests may contain API keys.
        raise ToolException(f"{source} 网络不可达、超时或响应格式错误。请稍后重试，未生成替代数据。") from None


async def cached(key, ttl, fetch):
    entry = _cache.get(key)
    if entry and clock.monotonic() - entry[0] < ttl:
        _cache.move_to_end(key)
        return entry[1]
    value = await fetch()
    _cache[key] = (clock.monotonic(), value)
    _cache.move_to_end(key)
    while len(_cache) > 256:
        _cache.popitem(last=False)
    return value


async def resolve_location(location):
    location = location.strip()
    if not location or len(location) > 200:
        raise ToolException("请提供明确的城市、国家/地区，或 latitude,longitude 坐标。")
    match = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)\s*[,，]\s*([+-]?\d+(?:\.\d+)?)\s*", location)
    if match:
        lat, lon = map(float, match.groups())
        if not -90 <= lat <= 90 or not -180 <= lon <= 180:
            raise ToolException("纬度须在 -90 到 90，经度须在 -180 到 180。")
        return {"name": location, "latitude": lat, "longitude": lon, "elevation_m": 0, "timezone": None, "note": "未提供海拔，使用海平面 0 米。"}

    async def fetch():
        key = os.getenv("OPEN_METEO_API_KEY", "").strip()
        host = "customer-geocoding-api.open-meteo.com" if key else "geocoding-api.open-meteo.com"
        params = {"name": location, "count": 5, "language": "zh", "format": "json"}
        if key:
            params["apikey"] = key
        result = await request_json(f"https://{host}/v1/search", params, "Open-Meteo 地点查询")
        candidates = result.get("results", [])
        if not candidates:
            raise ToolException("未找到地点，请提供英文城市名、国家/地区或 latitude,longitude 坐标。")
        exact = [c for c in candidates if c.get("name", "").casefold() == location.casefold()]
        choices = exact or candidates
        if len(choices) != 1:
            names = [f"{c.get('name')} / {c.get('admin1', '')} / {c.get('country', '')}" for c in choices]
            raise ToolException("地点有歧义，请确认城市/地区或提供坐标：" + "；".join(names))
        c = choices[0]
        return {"name": c["name"], "country": c.get("country"), "region": c.get("admin1"),
                "latitude": c["latitude"], "longitude": c["longitude"],
                "elevation_m": c.get("elevation", 0), "timezone": c.get("timezone")}

    return await cached(("geo", location), 86400, fetch)


async def weather_forecast(location, date, units):
    try:
        day = Date.fromisoformat(date)
    except ValueError:
        raise ToolException("天气日期必须使用 YYYY-MM-DD 格式。") from None
    place = await resolve_location(location)
    if place["timezone"]:
        today = datetime.now(ZoneInfo(place["timezone"])).date()
        if not today <= day <= today + timedelta(days=15):
            raise ToolException("天气仅支持观测地点今天起未来 16 天的预报，请调整日期。")
    key = os.getenv("OPEN_METEO_API_KEY", "").strip()
    host = "customer-api.open-meteo.com" if key else "api.open-meteo.com"
    params = {"latitude": place["latitude"], "longitude": place["longitude"], "timezone": "auto",
              "start_date": date, "end_date": date, "temperature_unit": units,
              "hourly": "temperature_2m,cloud_cover,precipitation_probability,wind_speed_10m,visibility,is_day"}
    if key:
        params["apikey"] = key

    async def fetch():
        data = await request_json(f"https://{host}/v1/forecast", params, "Open-Meteo 天气")
        if data.get("error") or "hourly" not in data or "time" not in data["hourly"]:
            raise ToolException("Open-Meteo 未返回预报，请确认日期在未来 16 天内。")
        try:
            local_today = datetime.now(ZoneInfo(data["timezone"])).date()
        except (KeyError, TypeError, ValueError):
            raise ToolException("Open-Meteo 未返回有效时区，无法确定预报日期。") from None
        if not local_today <= day <= local_today + timedelta(days=15):
            raise ToolException("天气仅支持观测地点今天起未来 16 天的预报，请调整日期。")
        hourly = data["hourly"]
        names = params["hourly"].split(",")
        if not hourly["time"] or any(len(hourly.get(n, [])) != len(hourly["time"]) for n in names):
            raise ToolException("Open-Meteo 小时数据缺失，无法可靠读取预报。")
        return {"source": "Open-Meteo", "source_url": "https://open-meteo.com/", "data_kind": "forecast",
                "retrieved_at": datetime.now(timezone.utc).isoformat(), "location": place, "date": date,
                "timezone": data.get("timezone"), "utc_offset_seconds": data.get("utc_offset_seconds"),
                "units": data.get("hourly_units", {}),
                "hourly": [{"time": t, **{n: hourly[n][i] for n in names}} for i, t in enumerate(hourly["time"])],
                "note": "数值天气预报，不是现场实测；null 表示缺测，不可视为零。请匹配观测地点当地小时。"}

    return await cached(("weather", place["latitude"], place["longitude"], date, units, bool(key)), 600, fetch)


def parse_horizons(data):
    # The public endpoint currently reports 1.2 while its docs advertise 1.3.
    # Both share the CSV schema used here; still reject unknown API versions.
    if data.get("signature", {}).get("version") not in {"1.2", "1.3"}:
        raise ToolException("NASA Horizons API 版本变化或缺少版本信息，请检查接口兼容性。")
    text = data.get("result", "")
    if data.get("error") or "$$SOE" not in text or "$$EOE" not in text:
        raise ToolException("NASA Horizons 未返回星历，请检查地点、时间和目标参数。")
    before, rows = text.split("$$SOE", 1)
    header = next((line for line in reversed(before.splitlines()) if "Date__(UT)__" in line and "," in line), None)
    rows = [line.strip() for line in rows.split("$$EOE", 1)[0].splitlines() if line.strip()]
    if header is None or len(rows) != 1:
        raise ToolException("NASA Horizons 表格结构变化或时间点数量异常，未解析星历。")
    columns, values = next(csv.reader([header])), next(csv.reader(rows))
    if len(columns) != len(values):
        raise ToolException("NASA Horizons 列数不匹配，未解析星历。")
    fields = dict(zip((c.strip() for c in columns), (v.strip() for v in values)))

    def number(label, required=False):
        value = fields.get(label)
        if value in (None, "", "n.a.", "NaN"):
            if required:
                raise ToolException(f"NASA Horizons 缺少 {label}，无法判断目标位置。")
            return None
        try:
            result = float(value)
            if not math.isfinite(result):
                raise ValueError()
            return result
        except ValueError:
            raise ToolException("NASA Horizons 数值格式异常，未生成替代值。") from None

    elevation = number("Elev_(a-app)", True)
    return {"azimuth_deg": number("Azi_(a-app)", True), "elevation_deg": elevation,
            "above_horizon": elevation > 0, "apparent_magnitude": number("APmag"), "illuminated_percent": number("Illu%")}


async def astronomy_ephemeris(location, time, equipment):
    try:
        instant = datetime.fromisoformat(time.replace("Z", "+00:00"))
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError()
    except ValueError:
        raise ToolException("天文时间须含时区偏移，例如 2026-11-05T20:00:00+08:00，请先确认时区。") from None
    contact = os.getenv("NASA_CONTACT", "").strip()
    if not contact or any(ch in contact for ch in "\r\n"):
        raise ToolException("请在 backend/.env 填写 NASA_CONTACT（联系邮箱或项目联系网址）。Horizons 无需 API Key，但要求 User-Agent 带有效联系方式。")
    place = await resolve_location(location)
    utc = instant.astimezone(timezone.utc)
    stamp = utc.strftime("%Y-%m-%d %H:%M:%S.%f")
    results = []
    # JPL fair-use: one request at a time, including concurrent Agent runs.
    async with _horizons_lock:
        for target, name in TARGETS:
            params = {"format": "json", "COMMAND": f"'{target}'", "OBJ_DATA": "'NO'", "MAKE_EPHEM": "'YES'",
                      "EPHEM_TYPE": "'OBSERVER'", "CENTER": "'coord@399'", "COORD_TYPE": "'GEODETIC'",
                      "SITE_COORD": f"'{place['longitude']},{place['latitude']},{(place.get('elevation_m') or 0) / 1000}'",
                      "TLIST": f"'{stamp}'", "TLIST_TYPE": "'CAL'", "TIME_TYPE": "'UT'",
                      "QUANTITIES": "'4,9,10'", "CSV_FORMAT": "'YES'", "APPARENT": "'AIRLESS'"}

            async def fetch(params=params):
                data = await request_json("https://ssd.jpl.nasa.gov/api/horizons.api", params, "NASA/JPL Horizons",
                                          {"User-Agent": f"Orbit-PBL/0.1 ({contact})"})
                return {**parse_horizons(data), "retrieved_at": datetime.now(timezone.utc).isoformat()}

            value = await cached(("horizons", place["latitude"], place["longitude"], place.get("elevation_m"), stamp, target), 86400, fetch)
            results.append({"id": target, "name": name, **value})
    sun = results.pop()
    return {"source": "NASA/JPL Horizons", "source_url": "https://ssd.jpl.nasa.gov/horizons/", "data_kind": "computed_ephemeris",
            "location": place, "time": instant.isoformat(), "time_utc": utc.isoformat(), "equipment": equipment,
            "targets": results, "sun_elevation_deg": sun["elevation_deg"],
            "note": "方位角从正北顺时针计；位置为无大气折射的站心星历。高于地平线不等于可见，需结合太阳高度、天气、遮挡和设备。亮度/照明率缺失为 null。不是现场实测，未计算设备分辨率。切勿用光学设备直视太阳。"}
