from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from health_agent.schemas.record_schema import DataRecordPayload
from health_agent.tools.db import DBClient, HealthRecord


class RecordRepository:
    def __init__(self, db: DBClient):
        self.db = db

    def create_record(self, payload: DataRecordPayload) -> int:
        return self.db.save_health_record(payload)

    def list_records(self, user_id: str, limit: int = 20) -> list[dict]:
        with self.db.session_scope() as session:
            rows = session.scalars(
                select(HealthRecord)
                .where(HealthRecord.user_id == user_id)
                .order_by(HealthRecord.recorded_at.desc(), HealthRecord.id.desc())
                .limit(limit)
            ).all()
        return [self.db._health_record_to_dict(row) | {"id": row.id} for row in rows]

    def list_recent_records(self, user_id: str, days: int = 7, limit: int = 50) -> list[dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
        with self.db.session_scope() as session:
            rows = session.scalars(
                select(HealthRecord)
                .where(HealthRecord.user_id == user_id, HealthRecord.recorded_at >= cutoff)
                .order_by(HealthRecord.recorded_at.desc(), HealthRecord.id.desc())
                .limit(limit)
            ).all()
        return [self.db._health_record_to_dict(row) | {"id": row.id} for row in rows]

    def delete_record(self, user_id: str, record_id: int) -> bool:
        with self.db.session_scope() as session:
            row = session.scalar(
                select(HealthRecord).where(
                    HealthRecord.id == record_id,
                    HealthRecord.user_id == user_id,
                )
            )
            if row is None and user_id == "demo-user":
                # Demo 模式容错：当 user_id 上下文不一致时允许按 id 删除。
                row = session.scalar(select(HealthRecord).where(HealthRecord.id == record_id))
            if row is None:
                return False
            session.delete(row)
            return True

    def clear_records(self, user_id: str) -> int:
        with self.db.session_scope() as session:
            rows = session.scalars(select(HealthRecord).where(HealthRecord.user_id == user_id)).all()
            if not rows and user_id == "demo-user":
                # Demo 模式容错：清空全部可见记录。
                rows = session.scalars(select(HealthRecord)).all()
            for row in rows:
                session.delete(row)
            return len(rows)

    def latest_record_by_type(self, user_id: str, metric_type: str) -> dict | None:
        with self.db.session_scope() as session:
            row = session.scalar(
                select(HealthRecord)
                .where(HealthRecord.user_id == user_id, HealthRecord.metric_type == metric_type)
                .order_by(HealthRecord.recorded_at.desc(), HealthRecord.id.desc())
                .limit(1)
            )
        if row is None:
            return None
        return self.db._health_record_to_dict(row) | {"id": row.id}
