from __future__ import annotations

from health_agent.schemas.agent_schema import AgentResponse
from health_agent.schemas.record_schema import DataRecordPayload
from health_agent.tools.db import DBClient


class DataAgent:
    def __init__(self, db: DBClient):
        self.db = db

    def run(self, user_id: str, parsed: dict) -> dict:
        metrics = parsed.get("metrics", [])
        if not metrics:
            raise ValueError("未识别到可记录的健康指标。")
        metric = metrics[0]
        payload = DataRecordPayload(
            user_id=user_id,
            metric_type=metric["metric_type"],
            metric_value=str(metric["metric_value"]),
            unit=metric.get("unit", ""),
        )
        record_id = self.db.save_health_record(payload)
        trend = self.db.query_metric_trend(user_id, payload.metric_type, days=7)
        answer = (
            f"已记录 {payload.metric_type}={payload.metric_value}{payload.unit}。"
            f" 最近7天内共找到 {len(trend)} 条同类记录。"
        )
        result = AgentResponse(
            answer=answer,
            current_agent="data_agent",
            risk_level="low",
            citations=[],
            data={"record_id": record_id, "record": payload.model_dump(), "trend": trend[:5]},
        )
        return result.model_dump()
