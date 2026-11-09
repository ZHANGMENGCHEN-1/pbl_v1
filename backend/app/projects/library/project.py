from ...shared.settings import models
from .prompt import BLOCKS, INITIAL_ORDER, INTRO, ENDING, TEMPLATE

PROJECT_ID = "library-recommendation"
ACTIVITY_IDS = ["group_books", "explain_algorithm", "explore_2d", "recommend_purchase"]
TOOLS = {
    "inspect_dataset": {"name": "数据查看工具", "description": "帮你查看选中的表，看看有哪些数据。", "parameters": "dataset_id · preview_rows"},
    "run_kmeans_analysis": {"name": "聚类分析工具", "description": "按你选的两列数据来分组，算出每组有多少条。", "parameters": "使用当前已保存的实验设置"},
}
ACTIVITIES = [
    {"id": ACTIVITY_IDS[0], "title": "活动一：给五本书分组", "phase": "计划与体验", "dataset_id": "library_sample_1d", "tools": ["inspect_dataset"],
     "body": "先试着把五本书分成两组。每算一轮，看看分组和中心有什么变化。",
     "instruction": "1. 选两个中心点。\n可以在数轴上点击，也可以输入数字。\n\n2. 点“计算一轮”。\n看看每本书分到了哪一组，中心变成了多少。\n\n3. 用新中心继续算。\n分组稳定后，点右下角“提交结果”。"},
    {"id": ACTIVITY_IDS[1], "title": "活动二：给助手排步骤", "phase": "监控 · 系统指令", "dataset_id": "library_sample_1d", "tools": ["inspect_dataset"],
     "body": "刚才你已经试过分组。现在给七个步骤排个顺序，教助手先做什么、后做什么。",
     "instruction": "1. 拖动七张卡片。\n把先做的放上面，后做的放下面。\n\n2. 想一想哪些步骤要重复。\n右边会自动生成助手的做事步骤。\n\n3. 点“提交结果”。\n检查步骤后提交，就能进入下一活动。"},
    {"id": ACTIVITY_IDS[2], "title": "活动三：把借阅记录分成两组", "phase": "监控 · 工具与证据", "dataset_id": "library_books_2d", "tools": ["inspect_dataset", "run_kmeans_analysis"],
     "body": "让助手用借阅次数和借阅时长，把150条记录分成两组。你要记录每组有多少条。",
     "instruction": "1. 选择数据。\n点“数据查看工具”，选表，再点“查看这张表”。点“聚类分析工具”，选要比较的两列。\n\n2. 告诉助手要做什么。\n在下面写清要分哪张表、分成几组、想知道什么，再点“开始运行”。\n\n3. 看结果，自己填写。\n检查两组数量，再点右下角“提交结果”，对照回答填写。"},
    {"id": ACTIVITY_IDS[3], "title": "活动四：帮图书馆选书", "phase": "调整与反思", "dataset_id": "reading_interest_students", "tools": ["inspect_dataset", "run_kmeans_analysis"],
     "body": "图书馆准备买1000册书。请根据同学们的阅读兴趣，决定买哪几类书、每类买多少，并说说理由。",
     "instruction": "1. 选择数据。\n查看阅读兴趣表，选好分组要用的两列。\n\n2. 请助手帮忙分析。\n写清买书任务，再点“开始运行”，看看助手给了什么建议。\n\n3. 写下你的买书方案。\n点右下角“提交结果”，填写书的类型、数量、理由和你的发现。合计买1000册。"},
]



def default_config():
    return {"model": models()[0], "temperature": 0.3,
            "prompt_steps": [],
            "system_prompt": "你是计算助手。帮助学生理解 K-Means，依据工具结果解释分组；不编造人数、中心或图书。数据和计算须通过工具核查。采购建议须区分调查证据与价值判断，给出合计 1000 册的类型建议，如实说明实际数据来源和样本局限。",
            "inspect_dataset": {"enabled": True}, "run_kmeans_analysis": {"enabled": True},
            "experiment": {"dataset_id": "library_sample_1d", "features": ["borrow_count"], "k": 2, "scaling": "none", "seed": 42}}


def project():
    return {"id": PROJECT_ID, "name": "图书馆采购推荐", "description": "从手工分组到智能体辅助采购决策", "models": models(), "activities": ACTIVITIES, "tools": TOOLS, "prompt_scaffold": {"blocks": BLOCKS, "initial_order": INITIAL_ORDER, "intro": INTRO, "ending": ENDING, "template": TEMPLATE}}


TASK_PROMPTS = {
    "explore_2d": "本活动替换前一活动的数据与具体任务，保留七步算法。使用当前选定的150条二维借阅数据及两个特征，调用完整聚类工具，K=2。以工具实际返回为准报告两组各多少条、合计150条。原Prompt中的五本书和2、11只是前一活动示例，不作为本次数据或二维初始中心。",
    "recommend_purchase": "本活动替换前一活动的数据与具体任务，保留七步算法。根据学生实际选择的数据表和特征进行分析，不自动换表。任务目标是利用阅读兴趣证据提出采购建议；只有所选表包含相关字段时，才可解释内容偏好（文艺到知识）和时长偏好（较短到较长）。调用完整聚类工具（默认K=2），根据每组中心解释偏好，根据人数比例提出采购类型和数量，合计1000册。可以为少数需求调整分配，但要说明依据。不编造具体书名，不把样本当成全校调查。",
}
