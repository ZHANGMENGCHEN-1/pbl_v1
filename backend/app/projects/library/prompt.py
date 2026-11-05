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
INTRO = "你是计算助手，使用K-means算法对学生选择的数据进行聚类分析。请按照下面的步骤执行并解释，不跳过步骤。"
ENDING = "使用学生选择的数据表、数值特征、分组数量K及其他已保存参数进行K-means聚类。先调用数据查看工具了解字段和数据，再调用本活动可用的聚类工具，以实际结果解释分组、各组数量和中心含义，不编造数据或工具结果。按工具采用的距离计算方式分组，重复分配数据和更新中心，直到达到停止条件；距离并列、空组及未收敛情况如实说明。保留计算精度，展示时可取近似值。结合当前任务解释结果及其局限，不把聚类结果直接当作决策结论。"
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
