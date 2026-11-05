"""Registered workbook loading only; users and models cannot supply file paths."""
from pathlib import Path
import hashlib
import json
import math
from openpyxl import load_workbook
from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[3] / "datasets" / "library"
FIELDS = {
    "borrow_count": {"label": "借阅次数", "unit": "次"},
    "borrow_days": {"label": "借阅总时长", "unit": "天"},
    "content_preference": {"label": "内容偏好", "unit": "0 文艺 → 100 知识", "range": [0, 100]},
    "duration_preference": {"label": "时长偏好", "unit": "0 短时 → 100 长时", "range": [0, 100]},
}


def manifest():
    return json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))


def fields(entry):
    definitions = {**FIELDS, **entry.get("field_definitions", {})}
    if any(key not in definitions for key in entry["features"]):
        raise HTTPException(422, "数据表的数值字段缺少定义")
    return [{"id": key, **definitions[key]} for key in entry["features"]]


def available(activity):
    """Only expose tables registered for the current learning activity."""
    return [{"id": key, "name": entry["name"], "source": entry["source"], "demo": entry["demo"], "fields": fields(entry), "dimensions": len(entry["features"])}
            for key, entry in manifest().items() if activity in entry.get("activities", [])]


def require_dataset(activity, dataset_id):
    if dataset_id not in {entry["id"] for entry in available(activity)}:
        raise HTTPException(403, "当前活动不能使用这张数据表")


def load(dataset_id):
    entry = manifest().get(dataset_id)
    if not entry:
        raise HTTPException(404, "数据集不存在")
    path = (ROOT / entry["file"]).resolve()
    if not path.is_relative_to(ROOT.resolve()):
        raise HTTPException(422, "数据表路径不合法")
    book = load_workbook(path, read_only=True, data_only=True)
    try:
        rows = list(book.active.values)
    finally:
        book.close()
    if not rows:
        raise HTTPException(422, "数据表为空")
    header = [entry.get("column_map", {}).get(value, value) for value in rows[0]]
    if not set(entry["features"]) <= set(header):
        raise HTTPException(422, "数据表缺少已配置的数值列")
    records = [dict(zip(header, row)) for row in rows[1:] if any(v is not None for v in row)]
    for i, row in enumerate(records, 1):
        row.setdefault("id", f"R{i:03}")
        row.setdefault("name", f"记录{i:03}")
    version = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return {"id": dataset_id, **entry, "version": version, "fields": fields(entry), "records": records, "row_count": len(records)}


def preview(dataset_id, count=10):
    value = load(dataset_id)
    issues = []
    definitions = {f["id"]: f for f in value["fields"]}
    for i, row in enumerate(value["records"]):
        for key in value["features"]:
            v = row.get(key)
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                issues.append({"row": i + 1, "field": key, "reason": "缺失或非有限数值"})
            elif "range" in definitions[key] and not definitions[key]["range"][0] <= v <= definitions[key]["range"][1]:
                issues.append({"row": i + 1, "field": key, "reason": "超出字段量表范围"})
    return {**{k: v for k, v in value.items() if k != "records"}, "preview": value["records"][:count], "issues": issues}
