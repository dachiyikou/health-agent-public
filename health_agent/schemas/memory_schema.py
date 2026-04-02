from __future__ import annotations

from pydantic import BaseModel, Field


class UserMemoryPayload(BaseModel):
    user_id: str
    memory_type: str
    content: str
    summary: str = ""
    importance: float = 0.5
    source_message_id: int | None = None
    is_active: bool = True
    expires_at: str | None = None


class UserProfilePayload(BaseModel):
    user_id: str
    display_name: str | None = None
    age_range: str | None = None
    gender: str | None = None
    height_cm: str | None = None
    weight_kg: str | None = None
    blood_type: str | None = None
    chronic_diseases: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    long_term_medications: list[str] = Field(default_factory=list)
    timezone: str | None = None
    profile_summary: str = ""


class SessionSummaryPayload(BaseModel):
    session_id: str
    user_id: str
    summary: str
