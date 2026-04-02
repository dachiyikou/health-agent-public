from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Iterator

from sqlalchemy import Boolean, Float, Integer, String, Text, create_engine, delete, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from health_agent.config import DATABASE_URL
from health_agent.schemas.memory_schema import UserMemoryPayload, UserProfilePayload
from health_agent.schemas.record_schema import DataRecordPayload, ReminderPayload


def utcnow() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _to_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def _from_json(value: str | None, default: Any) -> Any:
    if not value:
        return default
    return json.loads(value)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String, nullable=True)
    age_range: Mapped[str | None] = mapped_column(String, nullable=True)
    gender: Mapped[str | None] = mapped_column(String, nullable=True)
    height_cm: Mapped[str | None] = mapped_column(String, nullable=True)
    weight_kg: Mapped[str | None] = mapped_column(String, nullable=True)
    blood_type: Mapped[str | None] = mapped_column(String, nullable=True)
    chronic_diseases: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_term_medications: Mapped[str | None] = mapped_column(Text, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[str] = mapped_column(String, nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class UserMemory(Base):
    __tablename__ = "user_memories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    memory_type: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    importance: Mapped[float] = mapped_column(Float, nullable=False)
    source_message_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    expires_at: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class HealthRecord(Base):
    __tablename__ = "health_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    metric_type: Mapped[str] = mapped_column(String, nullable=False)
    metric_value: Mapped[str] = mapped_column(String, nullable=False)
    unit: Mapped[str | None] = mapped_column(String, nullable=True)
    recorded_at: Mapped[str | None] = mapped_column(String, nullable=True)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Medication(Base):
    __tablename__ = "medications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    drug_name: Mapped[str] = mapped_column(String, nullable=False)
    dosage: Mapped[str | None] = mapped_column(String, nullable=True)
    frequency: Mapped[str | None] = mapped_column(String, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class Reminder(Base):
    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    reminder_type: Mapped[str] = mapped_column(String, nullable=False)
    target_name: Mapped[str] = mapped_column(String, nullable=False)
    cron_expr: Mapped[str | None] = mapped_column(String, nullable=True)
    local_time: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column("metadata", Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    session_id: Mapped[str | None] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)


class DBClient:
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url
        self.engine = create_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False} if database_url.startswith("sqlite") else {},
        )
        self.SessionLocal = sessionmaker(bind=self.engine, autoflush=False, autocommit=False, expire_on_commit=False)

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def init_tables(self) -> None:
        Base.metadata.create_all(self.engine)
        self._ensure_sqlite_columns()

    def _ensure_sqlite_columns(self) -> None:
        if not self.database_url.startswith("sqlite"):
            return
        with self.engine.begin() as connection:
            existing = {
                row[1]
                for row in connection.exec_driver_sql("PRAGMA table_info(user_profiles)").fetchall()
            }
            for name, ddl in (
                ("display_name", "ALTER TABLE user_profiles ADD COLUMN display_name VARCHAR"),
                ("height_cm", "ALTER TABLE user_profiles ADD COLUMN height_cm VARCHAR"),
                ("weight_kg", "ALTER TABLE user_profiles ADD COLUMN weight_kg VARCHAR"),
                ("blood_type", "ALTER TABLE user_profiles ADD COLUMN blood_type VARCHAR"),
            ):
                if name not in existing:
                    connection.exec_driver_sql(ddl)

    def create_user(self, user_id: str, username: str | None = None) -> None:
        now = utcnow()
        with self.session_scope() as session:
            user = session.get(User, user_id)
            if user is None:
                user = User(id=user_id, username=username, created_at=now, updated_at=now)
                session.add(user)
            else:
                if username:
                    user.username = username
                user.updated_at = now

    def ensure_session(self, user_id: str, session_id: str, title: str | None = None) -> None:
        self.create_user(user_id)
        with self.session_scope() as session:
            chat_session = session.get(ConversationSession, session_id)
            if chat_session is None:
                session.add(
                    ConversationSession(
                        id=session_id,
                        user_id=user_id,
                        title=title or "健康会话",
                        started_at=utcnow(),
                        ended_at=None,
                        status="active",
                    )
                )

    def save_message(self, session_id: str, role: str, content: str, message_type: str = "chat") -> int:
        with self.session_scope() as session:
            row = ConversationMessage(
                session_id=session_id,
                role=role,
                content=content,
                message_type=message_type,
                created_at=utcnow(),
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def get_recent_messages(self, session_id: str, limit: int = 8) -> list[dict[str, Any]]:
        with self.session_scope() as session:
            rows = session.scalars(
                select(ConversationMessage)
                .where(ConversationMessage.session_id == session_id)
                .order_by(ConversationMessage.id.desc())
                .limit(limit)
            ).all()
        items = [self._message_to_dict(row) for row in rows]
        return list(reversed(items))

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        with self.session_scope() as session:
            rows = session.scalars(
                select(ConversationSession)
                .where(ConversationSession.user_id == user_id)
                .order_by(ConversationSession.started_at.desc())
            ).all()
        return [self._session_to_dict(row) for row in rows]

    def delete_session(self, user_id: str, session_id: str) -> None:
        with self.session_scope() as session:
            chat_session = session.get(ConversationSession, session_id)
            if chat_session is None or chat_session.user_id != user_id:
                return
            session.execute(delete(ConversationMessage).where(ConversationMessage.session_id == session_id))
            session.delete(chat_session)

    def clear_sessions(self, user_id: str) -> None:
        with self.session_scope() as session:
            session_ids = session.scalars(
                select(ConversationSession.id).where(ConversationSession.user_id == user_id)
            ).all()
            if session_ids:
                session.execute(delete(ConversationMessage).where(ConversationMessage.session_id.in_(session_ids)))
            session.execute(delete(ConversationSession).where(ConversationSession.user_id == user_id))

    def save_profile(self, payload: UserProfilePayload) -> None:
        now = utcnow()
        with self.session_scope() as session:
            row = session.scalar(select(UserProfile).where(UserProfile.user_id == payload.user_id))
            if row is None:
                row = UserProfile(user_id=payload.user_id, updated_at=now)
                session.add(row)
            row.display_name = payload.display_name
            row.age_range = payload.age_range
            row.gender = payload.gender
            row.height_cm = payload.height_cm
            row.weight_kg = payload.weight_kg
            row.blood_type = payload.blood_type
            row.chronic_diseases = _to_json(payload.chronic_diseases)
            row.allergies = _to_json(payload.allergies)
            row.long_term_medications = _to_json(payload.long_term_medications)
            row.timezone = payload.timezone
            row.profile_summary = payload.profile_summary
            row.updated_at = now

    def get_profile(self, user_id: str) -> dict[str, Any] | None:
        with self.session_scope() as session:
            row = session.scalar(select(UserProfile).where(UserProfile.user_id == user_id))
        if row is None:
            return None
        return self._profile_to_dict(row)

    def save_memory(self, payload: UserMemoryPayload) -> int:
        now = utcnow()
        with self.session_scope() as session:
            row = UserMemory(
                user_id=payload.user_id,
                memory_type=payload.memory_type,
                content=payload.content,
                summary=payload.summary,
                importance=payload.importance,
                source_message_id=payload.source_message_id,
                is_active=payload.is_active,
                expires_at=payload.expires_at,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def list_memories(self, user_id: str, active_only: bool = True) -> list[dict[str, Any]]:
        stmt = select(UserMemory).where(UserMemory.user_id == user_id)
        if active_only:
            stmt = stmt.where(UserMemory.is_active.is_(True))
        stmt = stmt.order_by(UserMemory.importance.desc(), UserMemory.updated_at.desc())
        with self.session_scope() as session:
            rows = session.scalars(stmt).all()
        return [self._memory_to_dict(row) for row in rows]

    def save_health_record(self, payload: DataRecordPayload) -> int:
        with self.session_scope() as session:
            row = HealthRecord(
                user_id=payload.user_id,
                metric_type=payload.metric_type,
                metric_value=payload.metric_value,
                unit=payload.unit,
                recorded_at=payload.recorded_at or utcnow(),
                source=payload.source,
                note=payload.note,
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def query_metric_trend(self, user_id: str, metric_type: str, days: int = 7) -> list[dict[str, Any]]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat(timespec="seconds")
        with self.session_scope() as session:
            rows = session.scalars(
                select(HealthRecord)
                .where(
                    HealthRecord.user_id == user_id,
                    HealthRecord.metric_type == metric_type,
                    HealthRecord.recorded_at >= cutoff,
                )
                .order_by(HealthRecord.recorded_at.desc())
            ).all()
        return [self._health_record_to_dict(row) for row in rows]

    def save_medication(
        self,
        user_id: str,
        drug_name: str,
        dosage: str = "",
        frequency: str = "",
        start_date: str | None = None,
        end_date: str | None = None,
        note: str = "",
    ) -> int:
        with self.session_scope() as session:
            row = Medication(
                user_id=user_id,
                drug_name=drug_name,
                dosage=dosage,
                frequency=frequency,
                start_date=start_date,
                end_date=end_date,
                note=note,
                created_at=utcnow(),
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def get_user_medications(self, user_id: str) -> list[dict[str, Any]]:
        with self.session_scope() as session:
            rows = session.scalars(
                select(Medication)
                .where(Medication.user_id == user_id)
                .order_by(Medication.created_at.desc())
            ).all()
        return [self._medication_to_dict(row) for row in rows]

    def save_reminder(self, payload: ReminderPayload) -> int:
        now = utcnow()
        with self.session_scope() as session:
            row = Reminder(
                user_id=payload.user_id,
                reminder_type=payload.reminder_type,
                target_name=payload.target_name,
                cron_expr=payload.cron_expr,
                local_time=payload.local_time,
                timezone=payload.timezone,
                status=payload.status,
                metadata_json=_to_json(payload.metadata),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            session.flush()
            return int(row.id)

    def list_active_reminders(self, user_id: str | None = None) -> list[dict[str, Any]]:
        stmt = select(Reminder).where(Reminder.status == "active").order_by(Reminder.created_at.desc())
        if user_id:
            stmt = stmt.where(Reminder.user_id == user_id)
        with self.session_scope() as session:
            rows = session.scalars(stmt).all()
        return [self._reminder_to_dict(row) for row in rows]

    def delete_reminder(self, reminder_id: int) -> None:
        with self.session_scope() as session:
            row = session.get(Reminder, reminder_id)
            if row:
                row.status = "deleted"
                row.updated_at = utcnow()

    def audit(self, action: str, payload: dict[str, Any], user_id: str | None = None, session_id: str | None = None) -> None:
        with self.session_scope() as session:
            session.add(
                AuditLog(
                    user_id=user_id,
                    session_id=session_id,
                    action=action,
                    payload=_to_json(payload),
                    created_at=utcnow(),
                )
            )

    def _session_to_dict(self, row: ConversationSession) -> dict[str, Any]:
        return {
            "id": row.id,
            "title": row.title,
            "started_at": row.started_at,
            "ended_at": row.ended_at,
            "status": row.status,
        }

    def _message_to_dict(self, row: ConversationMessage) -> dict[str, Any]:
        return {
            "id": row.id,
            "session_id": row.session_id,
            "role": row.role,
            "content": row.content,
            "message_type": row.message_type,
            "created_at": row.created_at,
        }

    def _profile_to_dict(self, row: UserProfile) -> dict[str, Any]:
        return {
            "user_id": row.user_id,
            "display_name": row.display_name,
            "age_range": row.age_range,
            "gender": row.gender,
            "height_cm": row.height_cm,
            "weight_kg": row.weight_kg,
            "blood_type": row.blood_type,
            "chronic_diseases": _from_json(row.chronic_diseases, []),
            "allergies": _from_json(row.allergies, []),
            "long_term_medications": _from_json(row.long_term_medications, []),
            "timezone": row.timezone,
            "profile_summary": row.profile_summary or "",
            "updated_at": row.updated_at,
        }

    def _memory_to_dict(self, row: UserMemory) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "memory_type": row.memory_type,
            "content": row.content,
            "summary": row.summary,
            "importance": row.importance,
            "source_message_id": row.source_message_id,
            "is_active": row.is_active,
            "expires_at": row.expires_at,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    def _health_record_to_dict(self, row: HealthRecord) -> dict[str, Any]:
        return {
            "user_id": row.user_id,
            "metric_type": row.metric_type,
            "metric_value": row.metric_value,
            "unit": row.unit,
            "recorded_at": row.recorded_at,
            "source": row.source,
            "note": row.note,
        }

    def _medication_to_dict(self, row: Medication) -> dict[str, Any]:
        return {
            "user_id": row.user_id,
            "drug_name": row.drug_name,
            "dosage": row.dosage,
            "frequency": row.frequency,
            "start_date": row.start_date,
            "end_date": row.end_date,
            "note": row.note,
            "created_at": row.created_at,
        }

    def _reminder_to_dict(self, row: Reminder) -> dict[str, Any]:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "reminder_type": row.reminder_type,
            "target_name": row.target_name,
            "cron_expr": row.cron_expr,
            "local_time": row.local_time,
            "timezone": row.timezone,
            "status": row.status,
            "metadata": _from_json(row.metadata_json, {}),
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
