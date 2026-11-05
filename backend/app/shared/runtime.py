import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from langchain.agents import create_agent
from langchain_openai import ChatOpenAI


def text_content(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(v.get("text", "") for v in value if isinstance(v, dict))
    return str(value)


async def execute(config, user_input, *, tools, context):
    if not os.getenv("LLM_API_KEY"):
        raise ValueError("尚未配置 LLM_API_KEY。请在 backend/.env 中设置模型密钥后重启后端。")
    llm = ChatOpenAI(api_key=os.environ["LLM_API_KEY"], base_url=os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
                     model=config.model, temperature=config.temperature,
                     timeout=float(os.getenv("LLM_TIMEOUT_SECONDS", "60")),
                     max_tokens=int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "1200")),
                     max_retries=int(os.getenv("LLM_MAX_RETRIES", "0")), disable_streaming=True)
    agent = create_agent(model=llm, tools=tools,
                         system_prompt=config.system_prompt + "\n" + context + "\n回答要求：简洁直接，先给结论。普通回答不超过200个汉字，只给必要的数量、依据和局限；不要逐条复述原始数据、全部距离或每轮计算，不展开长篇推导。若任务要求JSON，保持指定JSON结构完整，解释字段用短句，不在JSON外重复回答。" + "\n当前北京时间：" + datetime.now(ZoneInfo("Asia/Shanghai")).isoformat())
    yield "llm_start", {"node": "brain", "message": "模型正在理解任务并选择工具"}
    answer = ""
    async with asyncio.timeout(float(os.getenv("RUN_TIMEOUT_SECONDS", "180"))):
        async for e in agent.astream_events({"messages": [{"role": "user", "content": user_input}]}, version="v2", config={"recursion_limit": 20}):
            kind = e["event"]
            data = e.get("data", {})
            if kind == "on_chat_model_start":
                yield "llm_start", {"node": "brain", "message": "模型正在生成响应"}
            elif kind == "on_chat_model_end":
                output = data.get("output")
                calls = getattr(output, "tool_calls", [])
                if not calls:
                    answer = text_content(getattr(output, "content", ""))
                yield "llm_end", {"node": "brain", "tool_calls": len(calls)}
            elif kind == "on_tool_start":
                yield "tool_call", {"node": e["name"], "tool": e["name"], "input": data.get("input"), "call_id": e["run_id"]}
            elif kind == "on_tool_end":
                output = data.get("output")
                status = getattr(output, "status", "success")
                if status == "error":
                    yield "tool_error", {"node": e["name"], "message": getattr(output, "content", "工具查询失败")}
                yield "tool_result", {"node": e["name"], "tool": e["name"], "status": status, "output": getattr(output, "content", output), "call_id": e["run_id"]}
            elif kind == "on_tool_error":
                yield "tool_error", {"node": e["name"], "message": "工具参数或执行错误，请检查当前配置与输入格式"}
    if not answer:
        raise ValueError("模型未返回文本回答，请检查所选模型是否支持 Tool Calling。")
    yield "final", {"node": "brain", "answer": answer}


def public_error(exc):
    # Never expose upstream request headers, URLs with tokens, or raw API errors.
    if isinstance(exc, ValueError) and str(exc).startswith(("尚未配置", "模型未返回")):
        return str(exc)
    if isinstance(exc, TimeoutError):
        return "运行超时，请稍后重试或缩短任务。"
    name = type(exc).__name__
    if "Timeout" in name:
        return "模型响应超时，本次运行未完成。请稍后重试；若反复发生，请检查模型服务响应速度或换用更快的模型。"
    if "Authentication" in name:
        return "模型服务鉴权失败，请检查后端 API Key。"
    if "RateLimit" in name:
        return "模型服务限流或额度不足，请稍后重试。"
    return "Agent 执行失败，请检查模型服务连接、模型工具调用能力及参数。错误类型：" + name
