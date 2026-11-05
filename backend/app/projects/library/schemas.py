from typing import Literal
from pydantic import BaseModel, Field


class Enabled(BaseModel):
    enabled: bool = True


class Experiment(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=100)
    features: list[str] = Field(min_length=1, max_length=3)
    k: int = Field(default=2, ge=2, le=4)
    scaling: Literal["none", "standard"] = "none"
    seed: int = Field(default=42, ge=0, le=100000)


class Config(BaseModel):
    model: str = Field(min_length=1, max_length=150)
    temperature: float = Field(ge=0, le=2)
    system_prompt: str = Field(min_length=1, max_length=12000)
    prompt_steps: list[str] = Field(default_factory=list, max_length=7)
    task_prompt: str = Field(default="", max_length=6000)
    inspect_dataset: Enabled
    run_kmeans_analysis: Enabled
    experiment: Experiment


class RunInput(BaseModel):
    activity_id: str
    revision: int = Field(ge=0)
    input: str = Field(min_length=1, max_length=6000)


class Prediction(BaseModel):
    previous_step_id: str | None = None
    labels: list[int] = Field(min_length=5, max_length=5)
    centers: list[list[float]] = Field(min_length=2, max_length=2)


class Payload(BaseModel):
    payload: dict


class CenterStep(BaseModel):
    centers: list[float] = Field(min_length=2, max_length=2)
    previous_step_id: str | None = None


class PlanInput(BaseModel):
    text: str = Field(min_length=6, max_length=4000)
