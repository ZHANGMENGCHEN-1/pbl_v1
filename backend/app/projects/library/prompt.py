"""Activity-two scaffold: seven blocks from the classroom worksheet."""
from fastapi import HTTPException

BLOCKS = [
    {"id": "data", "label": "获取原始数据"},
    {"id": "count", "label": "确定中心点的数量", "detail": "使用学生配置的分组数量K，设置K个中心点。"},
    {"id": "centers", "label": "选择中心点", "detail": "根据所选数据的特征维度，初始化K个中心点。"},
    {"id": "distance", "label": "计算每个数据到中心点的距离"},
    {"id": "assign", "label": "将每个数据分配到最近的中心点"},
    {"id": "update", "label": "计算每个簇内数据的平均值，并更新中心点"},
    {"id": "iterate", "label": "进行迭代计算", "detail": "重复计算距离、分组和更新中心，直到分组与中心不再变化。"},
]
ORDER = [b["id"] for b in BLOCKS]
INITIAL_ORDER = ["centers", "iterate", "data", "distance", "assign", "update", "count"]
INTRO = "你是计算助手，使用K-means算法对数据进行聚类分析。请按照下面的步骤执行并解释，不跳过步骤。"
ENDING = "请使用我选择的数据和设置，调用工具完成计算。根据工具结果说明各组数量和中心的意思，不要编造结果。"
TEMPLATE = INTRO + "\n\n我的计算步骤：\n" + "\n".join(f"{i}. 【请排列第{i}个步骤模块】" for i in range(1,8)) + "\n\n" + ENDING


def render(steps):
    if len(steps) != 7 or set(steps) != set(ORDER):
        raise HTTPException(422, "请完整排列七个步骤，每个模块使用一次")
    by_id = {b["id"]: b for b in BLOCKS}
    return INTRO + "\n\n我的计算步骤：\n" + "\n".join(f"{i}. {by_id[k]['label']}。{by_id[k].get('detail', '')}" for i,k in enumerate(steps,1)) + "\n\n" + ENDING


def validate(steps):
    render(steps)
    # Data preparation and choosing K may be interchanged. Both must precede
    # distance calculation; initialization must not be part of the loop.
    positions = {k: steps.index(k) for k in ORDER}
    dependencies = [("count","centers"),("data","distance"),("centers","distance"),("distance","assign"),("assign","update"),("update","iterate")]
    if any(positions[a] >= positions[b] for a,b in dependencies):
        raise HTTPException(422, "步骤还需要调整：先准备数据和中心，再计算距离、分组、更新中心，最后进行迭代计算。")


def upgrade_saved_prompt(text):
    """Replace only former scaffold phrases; preserve student order and edits."""
    replacements = {
        "你是计算助手，帮助七年级学生根据借阅次数把五本书分成2组。请按照下面的步骤执行并解释，不跳过步骤。": INTRO,
        "本次分为2组，中心点数量为2。": BLOCKS[1]["detail"],
        "例如选择2和11作为初始中心。": BLOCKS[2]["detail"],
        "先使用数据查看工具获取数据，不编造数据。计算时展示距离、分组和新中心；距离相同时归入第1组，空组保留原中心。保留计算精度，展示时可取近似值。说明迭代何时停止。": ENDING,
    }
    for old,new in replacements.items():
        text=text.replace(old,new)
    return text
