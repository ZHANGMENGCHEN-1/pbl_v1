"""Parse model-authored decisions; validate totals, never invent a model answer."""
import json
from fastapi import HTTPException

FORMAT = '''最终回答请输出JSON对象（可放在json代码块内）：{"answer":"给学生的中文解释","purchases":[{"group":0,"type":"根据中心概括的采购类型","quantity":500},{"group":1,"type":"另一类型","quantity":500}],"rationale":"结合实际组中心、人数与样本局限说明分配依据"}。group使用工具的0起始组号，覆盖所有非空组，各组仅一项，quantity为非负整数，总和1000。示例数量不是答案，必须根据实际工具结果决策。'''


def validate_purchases(rows, result):
    groups={g['label'] for g in result['groups'] if g['count']>0}
    if not isinstance(rows,list) or len(rows)!=len(groups):
        raise HTTPException(422,'采购表须为每个非空分组提供一项建议')
    for row in rows:
        if not isinstance(row,dict) or type(row.get('group')) is not int or row['group'] not in groups or not isinstance(row.get('type'),str) or not row['type'].strip() or len(row['type'])>500 or type(row.get('quantity')) is not int or row['quantity']<0:
            raise HTTPException(422,'采购建议需要有效分组、类型和非负整数数量')
    if {r['group'] for r in rows}!=groups or sum(r['quantity'] for r in rows)!=1000:
        raise HTTPException(422,'采购建议须覆盖所有非空组，数量合计1000册')


def parse(answer,result):
    for index,char in enumerate(answer):
        if char!='{':continue
        try:value,_=json.JSONDecoder().raw_decode(answer[index:])
        except ValueError:continue
        if not isinstance(value,dict) or 'purchases' not in value:continue
        validate_purchases(value['purchases'],result)
        if any(not isinstance(value.get(k),str) or len(value[k].strip())<6 for k in ['answer','rationale']):
            raise HTTPException(422,'Agent需说明采购建议、分配依据和样本局限')
        return {k:value[k] for k in ['answer','purchases','rationale']}
    raise HTTPException(422,'Agent未返回完整的采购表，请要求它给出各类数量、依据并重新运行')
