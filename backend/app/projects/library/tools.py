from fastapi import HTTPException
from langchain.tools import tool
from langchain_core.tools import ToolException
from . import engine
from .project import ACTIVITIES, ACTIVITY_IDS
from .datasets import load


def build_tools(session, activity, revision, config, run_id, dataset_version=None):
    version = dataset_version or load(config["experiment"]["dataset_id"])["version"]
    def call(fn, *args):
        try:
            if load(config["experiment"]["dataset_id"])["version"] != version:
                raise HTTPException(409, "运行期间数据已变化，请重新运行")
            return fn(session, activity, revision, *args)
        except HTTPException as exc:
            raise ToolException(str(exc.detail)) from None

    @tool
    def inspect_dataset(dataset_id: str, preview_rows: int = 5) -> dict:
        """Read the Excel table selected by the student: schema, units, source, preview and quality. Use dataset_id from the saved experiment configuration. Do not switch the student's table or guess file paths/column meanings."""
        return call(engine.inspect, dataset_id, preview_rows, run_id)

    @tool
    def run_kmeans_analysis() -> dict:
        """Run full K-Means on the student's saved experiment configuration. Returns real labels, group sizes, centers and iteration trace. No parameters: do not override the student's selected K/features/scaling/seed."""
        value = call(engine.full, run_id)
        # Full row assignments and iteration distances stay in SQLite and are
        # fetched by the results view; the model only needs decision evidence.
        keys = ["analysis_id", "dataset_id", "dataset_version", "source", "demo", "experiment", "fields", "sample_count", "groups", "converged", "warnings"]
        return {**{key: value[key] for key in keys}, "iteration_count": len(value["iterations"]), "excluded_count": len(value["excluded"])}

    available = ACTIVITIES[ACTIVITY_IDS.index(activity)]["tools"]
    result = [t for t in [inspect_dataset, run_kmeans_analysis] if t.name in available and config[t.name]["enabled"]]
    for t in result:
        t.handle_tool_error = True
    return result
