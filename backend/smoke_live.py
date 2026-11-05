"""Opt-in live provider smoke test. Uses the configured API and may incur costs."""
import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app.main import app  # Loads backend/.env before project defaults.
from app.projects.astronomy.runtime import execute, public_error
from app.projects.astronomy.project import default_config
from app.projects.astronomy.schemas import AgentConfig


async def main():
    config = AgentConfig(**default_config())
    calls = []
    date = (datetime.now(ZoneInfo("Asia/Shanghai")) + timedelta(days=1)).date().isoformat()
    try:
        async for kind, data in execute(config, f"请为{date}北京时间20:00（UTC+08:00）在北京（39.9,116.4）使用双筒望远镜的月球与行星观测活动制定计划。请查询天气与天体工具并标明数据来源。"):
            if kind == "tool_call":
                calls.append(data["tool"])
            print(json.dumps({"type": kind, "node": data.get("node"), "tool": data.get("tool"), "answer_length": len(data.get("answer", ""))}, ensure_ascii=False))
        print("Live provider completed. Tool calls: " + ", ".join(calls))
    except Exception as exc:
        print(public_error(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
