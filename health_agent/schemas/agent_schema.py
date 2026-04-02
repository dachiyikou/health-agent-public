from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source: str
    collection: str
    score: float
    chunk_id: str | None = None


class PlannerResult(BaseModel):
    intent: str
    route: str
    risk_level: str
    need_rag: bool = False
    need_memory_write: bool = False
    parsed: dict[str, Any] = Field(default_factory=dict)


class AgentResponse(BaseModel):
    answer: str
    current_agent: str
    risk_level: str = "low"
    citations: list[Citation] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)


class SymptomResult(AgentResponse):
    follow_up_questions: list[str] = Field(default_factory=list)
    triage_level: str = "self_care"


class DrugResult(AgentResponse):
    interaction_risk: str = "unknown"
    contraindications: list[str] = Field(default_factory=list)
