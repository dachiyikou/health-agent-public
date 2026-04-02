from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ChatMessagePayload(BaseModel):
    session_id: str
    role: str
    content: str
    message_type: str = "chat"


class HealthMetric(BaseModel):
    metric_type: str
    metric_value: str
    unit: str = ""
    recorded_at: str | None = None


class DataRecordPayload(BaseModel):
    user_id: str
    metric_type: str
    metric_value: str
    unit: str = ""
    recorded_at: str | None = None
    source: str = "chat"
    note: str = ""


class ManualRecordPayload(BaseModel):
    user_id: str
    record_type: str
    value: str
    unit: str = ""
    recorded_at: str | None = None
    note: str = ""


class ReminderCreatePayload(BaseModel):
    user_id: str
    title: str
    content: str = ""
    schedule_time: str
    recurrence: str = "daily"
    enabled: bool = True


class ReminderPayload(BaseModel):
    user_id: str
    reminder_type: str
    target_name: str
    cron_expr: str | None = None
    local_time: str | None = None
    timezone: str = "Asia/Shanghai"
    status: str = "active"
    metadata: dict[str, Any] = Field(default_factory=dict)
