import numpy as np
from fastapi import HTTPException
from .datasets import load


def matrix(experiment):
    data = load(experiment["dataset_id"])
    features = experiment["features"]
    definitions = {f["id"]: f for f in data["fields"]}
    if len(set(features)) != len(features) or not set(features) <= set(data["features"]):
        raise HTTPException(422, "特征必须是数据集中不同的数值字段")
    records, excluded = [], []
    for i, row in enumerate(data["records"]):
        values = [row.get(f) for f in features]
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not np.isfinite(v) or ("range" in definitions[f] and not definitions[f]["range"][0] <= v <= definitions[f]["range"][1]) for f, v in zip(features, values)):
            excluded.append({"row": i + 1, "reason": "缺失、非数值或量表越界"})
        else:
            records.append(row)
    x = np.array([[r[f] for f in features] for r in records], dtype=float)
    k = experiment["k"]
    if len(records) < k or len(np.unique(x, axis=0)) < k:
        raise HTTPException(422, "有效且不同的数据点不足，无法使用该 K 值")
    mean = x.mean(axis=0) if experiment["scaling"] == "standard" else np.zeros(x.shape[1])
    scale = x.std(axis=0) if experiment["scaling"] == "standard" else np.ones(x.shape[1])
    scale[scale == 0] = 1
    return data, records, excluded, x, (x - mean) / scale, mean, scale


def one_step(x, centers):
    centers = np.asarray(centers, dtype=float)
    if centers.ndim != 2 or centers.shape[1] != x.shape[1] or not np.isfinite(centers).all():
        raise HTTPException(422, "中心点维度不匹配或含非法数值")
    distances = np.linalg.norm(x[:, None, :] - centers[None, :, :], axis=2)
    labels = distances.argmin(axis=1)
    updated = centers.copy()
    warnings = []
    for i in range(len(centers)):
        group = x[labels == i]
        if len(group):
            updated[i] = group.mean(axis=0)
        else:
            # A transparent, deterministic policy, shared by step and full runs.
            warnings.append(f"第{i+1}组为空，本轮保留原中心；请检查初始中心或 K 值")
    return {"centers_before": centers.tolist(), "distances": distances.tolist(), "labels": labels.tolist(),
            "centers_after": updated.tolist(), "converged": bool(np.allclose(centers, updated, rtol=0, atol=1e-8)), "warnings": warnings}


def analyze(experiment, initial_centers=None, step_only=False):
    data, records, excluded, original, x, mean, scale = matrix(experiment)
    centers = np.asarray(initial_centers, dtype=float) if initial_centers is not None else x[np.random.default_rng(experiment["seed"]).choice(len(x), experiment["k"], replace=False)]
    if len(centers) != experiment["k"]:
        raise HTTPException(422, "初始中心数量必须等于 K")
    trace = []
    for _ in range(1 if step_only else 100):
        value = one_step(x, centers)
        trace.append(value)
        centers = np.array(value["centers_after"])
        if value["converged"]:
            break
    final = trace[-1]
    return {"dataset_id": data["id"], "dataset_version": data["version"], "dataset_name": data["name"], "source": data["source"], "demo": data["demo"],
            "experiment": experiment, "fields": [f for key in experiment["features"] for f in data["fields"] if f["id"] == key], "records": records, "excluded": excluded,
            "sample_count": len(records), "labels": final["labels"], "centers": final["centers_after"],
            "original_centers": (centers * scale + mean).tolist(), "scaling_mean": mean.tolist(), "scaling_scale": scale.tolist(),
            "groups": [{"label": i, "count": final["labels"].count(i), "proportion": final["labels"].count(i) / len(records), "center": (centers[i] * scale + mean).tolist()} for i in range(experiment["k"])],
            "iterations": trace, "converged": final["converged"], "warnings": final["warnings"]}
