from ...shared import runtime
from .tools import build_tools

CONTEXT = "运行环境说明：当前天气查询工具调用真实 Open-Meteo，天体查询工具调用真实 NASA/JPL Horizons，没有 Mock 回退。以本次工具返回的 source、data_kind 和错误为准，旧 Prompt 中关于模拟工具的说明不再适用。天气为预报，星历为计算数据，均不是现场实测。工具失败或字段缺失时如实说明，不能编造。Astronomy 固定查询月球、木星、土星及太阳；设备配置仅为建议上下文，不改变位置计算。"


async def execute(config, user_input):
    async for event in runtime.execute(config, user_input, tools=build_tools(config), context=CONTEXT):
        yield event


public_error = runtime.public_error
