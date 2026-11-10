from ...shared.settings import models
from .prompt import BLOCKS, INITIAL_ORDER, INTRO, ENDING, TEMPLATE

PROJECT_ID = "library-recommendation"
ACTIVITY_IDS = ["group_books", "explain_algorithm", "explore_2d", "recommend_purchase"]
TOOLS = {
    "inspect_dataset": {"name": "数据查看工具", "description": "读取学生选定的数据表，返回字段含义、数据量、来源与预览；完整分析使用同一张表。", "parameters": "dataset_id · preview_rows"},
    "run_kmeans_analysis": {"name": "聚类分析工具", "description": "依据已保存的特征、K 值和标准化设置完成聚类，返回各轮计算和图形证据。", "parameters": "使用当前已保存的实验设置"},
}
ACTIVITIES = [
    {"id": ACTIVITY_IDS[0], "title": "活动一：完成数据迭代计算", "phase": "计划与体验", "dataset_id": "library_sample_1d", "tools": ["inspect_dataset"],
     "body": "如何把数据分为两组？请你先指定两个中心点，把每个数据分给离它最近的中心，再计算各组平均值作为新中心。重复这个过程，直到分组稳定。",
     "instruction": "1. 在一维数轴上选择两个不同的初始中心，也可随机选择。\n\n2. 调用工具计算一轮，观察距离、分组与新中心。\n\n3. 再使用新中心计算下一轮，直到稳定。"},
    {"id": ACTIVITY_IDS[1], "title": "活动二：为计算助手编写步骤", "phase": "监控 · 系统指令", "dataset_id": "library_sample_1d", "tools": ["inspect_dataset"],
     "body": "现在，请你把七个步骤模块按合理顺序排列，补全计算助手的系统指令，告诉它先做什么、后做什么，以及哪些步骤需要重复。",
     "instruction": "点击计算助手大脑，将七个模块拖动排序，或用上移、下移调整。排序会自动填入半开放的系统指令，保存并提交即可。"},
    {"id": ACTIVITY_IDS[2], "title": "活动三：用Agent完成二维分组", "phase": "监控 · 工具与证据", "dataset_id": "library_books_2d", "tools": ["inspect_dataset", "run_kmeans_analysis"],
     "body": "复用活动二排好步骤的计算助手，给它配置数据与聚类工具。让计算助手把150条借阅数据按借阅次数和借阅时长分成2组，报告每组多少条，总数是否为150。",
     "instruction": "1. 选择正确的数据表\n点击“数据查看工具”，选择本活动需要的数据表，调用工具查看内容。\n\n2. 给智能体描述任务\n在下方输入框中，说清楚要分析什么数据、希望得到什么结果。\n\n3. 运行并检查结果\n点击“运行智能体”，检查它使用的数据、工具和两组数量，再填写并提交自己的结果。"},
    {"id": ACTIVITY_IDS[3], "title": "活动四：为图书馆作出采购决策", "phase": "调整与反思", "dataset_id": "reading_interest_students", "tools": ["inspect_dataset", "run_kmeans_analysis"],
     "body": "根据书籍内容偏好和阅读时长偏好进行分组。结合每组中心和人数，决定买什么类型的书、每类多少册，合计1000册。",
     "instruction": "1. 选择正确的数据表\n点击“数据查看工具”，选择本活动需要的数据表，调用工具查看内容。\n\n2. 给智能体描述任务\n在下方输入框中，说清楚要分析什么数据、希望得到什么结果。\n\n3. 运行并检查结果\n点击“运行智能体”，检查它使用的数据、工具和两组数量，再填写并提交自己的结果。\n\n4. 在整个过程中你有什么收获？填写你的反思，思考有哪里可以改进。"},

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
