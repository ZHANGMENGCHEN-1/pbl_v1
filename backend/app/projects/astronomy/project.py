from ...shared.settings import models

PROJECT_ID = "astronomy-lab"


def default_config():
    return {
        "model": models()[0], "temperature": 0.4,
        "system_prompt": "你是一位耐心的太阳系观测助手，帮助学生比较月球、木星、土星等目标并制定有依据的观测计划。先确认观测地点、当地日期时间与时区、设备；地点不明确时询问，不要猜测经纬度。需要天气或天体数据时自主调用可用工具。天体位置数据与天气数据应分别标明来源：NASA/JPL Horizons 提供太阳系天体星历，不提供天气、星座或深空天体目录。仅使用工具实际返回的字段；缺少地平高度、方位角、亮度或天气时明确说明无法判定，不要编造数值，也不要把位于地平线上方等同于肉眼可见。天气查询工具 使用真实 Open-Meteo 预报，天体查询工具 使用真实 NASA/JPL Horizons 计算星历，两者都不是现场实测。工具失败时如实说明，不得以模拟结果替代。请用中文回答，并提醒不要用光学设备直视太阳。",
        "weather": {"enabled": True, "units": "celsius"},
        "astronomy": {"enabled": True, "equipment": "binoculars"},
    }


def project():
    return {
        "id": PROJECT_ID, "name": "天文观测 Agent", "subtitle": "为月球与行星制定一份观测计划",
        "description": "构建一位太阳系观测助手，围绕月球、木星、土星等目标，学习让 Agent 结合天体位置与天气证据提出建议。通过 NASA/JPL Horizons 计算星历，结合 Open-Meteo 天气预报，形成可核查的观测建议。",
        "objectives": ["区分 NASA 天体星历与天气预报的用途", "用 Prompt 约束 Agent 核实地点、时间和数据来源", "观察工具调用，依据返回数据比较太阳系观测目标"],
        "models": models(),
        "steps": [
            {"title": "定义太阳系观测任务", "duration": "3 分钟", "tag": "明确问题", "body": "项目问题：指定地点和时间，月球、木星、土星中哪些值得观测？NASA/JPL Horizons 可查询太阳系天体随时间和观测位置变化的星历，不提供星座、星团或星系观测目录。智能体大脑负责比较证据，工具负责提供数据。", "instruction": "点击 智能体大脑，查看配置。为任务补齐城市或观测坐标、日期、当地时间与时区、观测设备，并选定月球或行星作为候选目标。先不要假定它们当晚可见。"},
            {"title": "设定有依据的回答规则", "duration": "5 分钟", "tag": "配置大脑", "body": "观测计划需要可核查的输入和来源。System Prompt 应要求 Agent 先确认地点与时间，只解释工具实际返回的数据。NASA 星历与天气预报来自不同服务；没有数据时，Agent 应指出缺口，而不是编造位置或可见性。", "instruction": "在 System Prompt 加入「先确认地点、当地时间和时区；只依据工具结果比较月球与行星；缺少位置或天气数据时说明无法判定；天气预报与计算星历不得称为现场实测，接口失败不得编造结果」，保存配置。"},
            {"title": "区分星历与天气工具", "duration": "4 分钟", "tag": "理解数据", "body": "Horizons 可查询指定太阳系目标的方位角、地平高度等星历；天气查询工具 的 Open-Meteo 接口用于查询云量、降水和风速。天体高于地平线只是观测条件之一，还要考虑天光、天气和设备。星历和预报不包含现场遮挡、光污染或设备分辨率，不能保证实际可见。", "instruction": "点击两个工具查看输入参数与配置。运行后展开工具返回：哪些是天气字段，哪些是天体字段？若没有地平高度或方位角，记录为数据缺口，不要让 Agent 补造数值。"},
            {"title": "比较目标并验证结论", "duration": "5 分钟", "tag": "运行实验", "body": "一份合格的结果应列出候选目标、数据来源、支持建议的证据和无法确认的条件。检查模型是否自主调用工具、是否正确传入地点和时间，以及是否仅凭高于地平线就保证实际可见。运行轨迹展示执行事件，不展示隐藏推理。", "instruction": "点击下方「试试示例」，比较月球、木星和土星的观测条件。再关闭 天气查询工具 重跑：Agent 是否说明缺少天气？提交包含数据来源、观测时区、目标方位角和地平高度的比较结果，并说明天气、天光与设备限制。"},
        ],
        "tools": {
            "weather": {"name": "天气查询工具", "description": "调用 Open-Meteo 获取指定地点未来 16 天内的逐小时温度、云量、降水概率、风速、能见度和昼夜标记。免费非商业接口无需 Key。", "parameters": [{"name": "location", "type": "string", "description": "城市名（建议含国家/地区），或 latitude,longitude"}, {"name": "date", "type": "YYYY-MM-DD", "description": "观测日期"}]},
            "astronomy": {"name": "天体查询工具", "description": "调用 NASA/JPL Horizons 查询月球、木星、土星的方位角、地平高度、亮度及照明率，并返回太阳高度。无需 API Key，后端需填写 NASA_CONTACT。设备仅用于建议，不改变星历。", "parameters": [{"name": "location", "type": "string", "description": "城市名或 latitude,longitude；同名城市需确认地区"}, {"name": "time", "type": "ISO datetime", "description": "当地 ISO 时间，必须包含 UTC 偏移，如 2026-11-05T20:00:00+08:00"}]},
        },
    }
