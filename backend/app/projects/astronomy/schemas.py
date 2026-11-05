from typing import Literal
from pydantic import BaseModel, Field


class WeatherConfig(BaseModel):
    enabled: bool = True
    units: Literal["celsius", "fahrenheit"] = "celsius"


class AstronomyConfig(BaseModel):
    enabled: bool = True
    equipment: Literal["naked_eye", "binoculars", "telescope"] = "binoculars"


class AgentConfig(BaseModel):
    model: str = Field(min_length=1, max_length=150)
    system_prompt: str = Field(min_length=1, max_length=12000)
    temperature: float = Field(ge=0, le=2)
    weather: WeatherConfig
    astronomy: AstronomyConfig


class RunRequest(BaseModel):
    input: str = Field(min_length=1, max_length=6000)
    config: AgentConfig


class Activity(BaseModel):
    action: Literal["learning_step_completed"]
    step: int = Field(ge=0, le=3)
