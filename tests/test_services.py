from datetime import datetime, timedelta
from types import SimpleNamespace

from health_agent.services.copilot_service import CopilotService
from health_agent.services.profile_service import ProfileService
from health_agent.services.record_service import RecordService
from health_agent.services.reminder_service import ReminderService
from health_agent.tools.db import DBClient


class FakeMemory:
    def __init__(self):
        self.persisted = []

    def read_profile(self, user_id: str):
        return {"user_id": user_id, "timezone": "Asia/Shanghai", "allergies": [], "chronic_diseases": [], "long_term_medications": [], "profile_summary": ""}

    def read_session_context(self, session_id: str):
        return []

    def maybe_persist(self, user_id: str, session_id: str, parsed: dict, source_message_id=None):
        self.persisted.append((user_id, session_id, parsed, source_message_id))
        return []


class FakeParser:
    def parse(self, message: str):
        if "体温" in message:
            return {
                "intent": "data_record",
                "metrics": [{"metric_type": "temperature", "metric_value": "37.8", "unit": "C"}],
                "schedule": {},
                "memory_facts": [],
                "symptoms": [],
                "drugs": [],
            }
        return {
            "intent": "reminder_set",
            "metrics": [],
            "schedule": {"local_time": "20:00", "cron_expr": "0 20 * * *"},
            "memory_facts": [],
            "symptoms": [],
            "drugs": [],
        }


class FakePlanner:
    def run(self, user_id: str, session_id: str, message: str, parsed: dict):
        route = "data_agent" if parsed["intent"] == "data_record" else "reminder_agent"
        return {"route": route, "need_memory_write": False, "risk_level": "low"}

    def build_clarification(self, parsed: dict):
        return {"answer": "clarify", "current_agent": "planner", "risk_level": "low", "citations": [], "data": {}}

    def build_general_chat(self, message: str, parsed: dict, profile: dict, session_ctx: list[dict]):
        return {"answer": "general", "current_agent": "general_chat_agent", "risk_level": "low", "citations": [], "data": {}}


class FakeDataAgent:
    def __init__(self, db: DBClient):
        self.db = db

    def run(self, user_id: str, parsed: dict):
        metric = parsed["metrics"][0]
        record_id = self.db.save_health_record(
            SimpleNamespace(
                user_id=user_id,
                metric_type=metric["metric_type"],
                metric_value=metric["metric_value"],
                unit=metric["unit"],
                recorded_at=None,
                source="chat",
                note="",
            )
        )
        return {
            "answer": "已记录体温",
            "current_agent": "data_agent",
            "risk_level": "low",
            "citations": [],
            "data": {"record_id": record_id},
        }


class FakeReminderAgent:
    def __init__(self, db: DBClient):
        self.db = db

    def run(self, user_id: str, parsed: dict, profile: dict):
        reminder_id = self.db.save_reminder(
            SimpleNamespace(
                user_id=user_id,
                reminder_type="custom",
                target_name="晚间提醒",
                cron_expr="0 20 * * *",
                local_time="20:00",
                timezone="Asia/Shanghai",
                status="active",
                metadata={"source": "chat"},
            )
        )
        return {
            "answer": "已创建提醒",
            "current_agent": "reminder_agent",
            "risk_level": "low",
            "citations": [],
            "data": {"reminder_id": reminder_id},
        }


class FakeScheduler:
    def __init__(self):
        self.synced = []
        self.removed = []

    def sync_job(self, reminder: dict):
        self.synced.append(reminder)

    def remove_job(self, reminder_id):
        self.removed.append(reminder_id)


def build_runtime(tmp_path):
    db = DBClient(database_url=f"sqlite:///{tmp_path / 'test.db'}")
    db.init_tables()
    scheduler = FakeScheduler()
    return SimpleNamespace(
        db=db,
        parser=FakeParser(),
        planner=FakePlanner(),
        data_agent=FakeDataAgent(db),
        reminder_agent=FakeReminderAgent(db),
        symptom_agent=None,
        drug_agent=None,
        memory=FakeMemory(),
        scheduler=scheduler,
        tracer=SimpleNamespace(log_event=lambda *args, **kwargs: None),
    )


def test_record_service_creates_record_and_profile_reads_it(tmp_path):
    runtime = build_runtime(tmp_path)
    record_service = RecordService(runtime)
    profile_service = ProfileService(runtime)

    created = record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.7",
            "unit": "C",
            "recorded_at": "2026-03-29T08:00:00",
            "note": "晨起体温",
        }
    )

    profile = profile_service.get_profile("demo-user")

    assert created["record"]["metric_type"] == "temperature"
    assert profile["recent_records"][0]["metric_type"] == "temperature"
    assert profile["stats"]["record_count"] == 1


def test_record_service_applies_default_unit_and_metric_label(tmp_path):
    runtime = build_runtime(tmp_path)
    record_service = RecordService(runtime)

    created = record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "blood_pressure",
            "value": "80/120",
            "unit": "",
            "recorded_at": "2026-03-29T08:00:00",
            "note": "",
        }
    )
    listed = record_service.list_records("demo-user")

    assert created["record"]["unit"] == "mmHg"
    assert listed[0]["metric_label"] == "血压"


def test_record_service_rejects_absurd_temperature_and_invalid_bp(tmp_path):
    runtime = build_runtime(tmp_path)
    record_service = RecordService(runtime)

    try:
        record_service.create_record(
            {
                "user_id": "demo-user",
                "record_type": "temperature",
                "value": "99",
                "unit": "C",
                "recorded_at": "2026-03-29T08:00:00",
                "note": "",
            }
        )
        assert False, "Expected ValueError for absurd temperature"
    except ValueError:
        pass

    try:
        record_service.create_record(
            {
                "user_id": "demo-user",
                "record_type": "blood_pressure",
                "value": "120/80",
                "unit": "mmHg",
                "recorded_at": "2026-03-29T08:00:00",
                "note": "",
            }
        )
        assert False, "Expected ValueError for invalid blood pressure format/order"
    except ValueError:
        pass

    before = len(record_service.list_records("demo-user", limit=50))
    future_time = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")
    try:
        record_service.create_record(
            {
                "user_id": "demo-user",
                "record_type": "heart_rate",
                "value": "80",
                "unit": "bpm",
                "recorded_at": future_time,
                "note": "",
            }
        )
        assert False, "Expected ValueError for future recorded_at"
    except ValueError:
        pass
    after = len(record_service.list_records("demo-user", limit=50))
    assert before == after


def test_record_service_can_delete_and_clear_records(tmp_path):
    runtime = build_runtime(tmp_path)
    record_service = RecordService(runtime)

    created_one = record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.7",
            "unit": "C",
            "recorded_at": "2026-03-29T08:00:00",
            "note": "",
        }
    )
    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "heart_rate",
            "value": "80",
            "unit": "bpm",
            "recorded_at": "2026-03-29T09:00:00",
            "note": "",
        }
    )

    deleted = record_service.delete_record("demo-user", created_one["record_id"])
    cleared = record_service.clear_records("demo-user")

    assert deleted["deleted_record_id"] == created_one["record_id"]
    assert cleared["cleared"] is True
    assert cleared["deleted_count"] >= 1


def test_record_service_list_records_supports_recent_days_filter(tmp_path):
    runtime = build_runtime(tmp_path)
    record_service = RecordService(runtime)

    old_time = (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds")
    recent_time = (datetime.now() - timedelta(days=1)).isoformat(timespec="seconds")
    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.5",
            "unit": "C",
            "recorded_at": old_time,
            "note": "old",
        }
    )
    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.7",
            "unit": "C",
            "recorded_at": recent_time,
            "note": "recent",
        }
    )

    recent_records = record_service.list_records("demo-user", limit=20, days=7)

    assert len(recent_records) == 1
    assert recent_records[0]["note"] == "recent"


def test_reminder_service_can_create_list_and_toggle(tmp_path):
    runtime = build_runtime(tmp_path)
    reminder_service = ReminderService(runtime)

    created = reminder_service.create_reminder(
        {
            "user_id": "demo-user",
            "title": "服药提醒",
            "content": "晚上吃药",
            "schedule_time": "20:00",
            "recurrence": "daily",
            "enabled": True,
        }
    )
    reminders = reminder_service.list_reminders("demo-user")
    toggled = reminder_service.toggle_reminder(created["id"], False)

    assert reminders[0]["target_name"] == "服药提醒"
    assert toggled["status"] == "paused"
    assert runtime.scheduler.removed == [created["id"]]


def test_reminder_service_can_delete_and_hide_deleted_reminders(tmp_path):
    runtime = build_runtime(tmp_path)
    reminder_service = ReminderService(runtime)

    created = reminder_service.create_reminder(
        {
            "user_id": "demo-user",
            "title": "服药提醒",
            "content": "晚上吃药",
            "schedule_time": "20:00",
            "recurrence": "daily",
            "enabled": True,
        }
    )
    reminder_service.toggle_reminder(created["id"], False)
    deleted = reminder_service.delete_reminder(created["id"])
    reminders = reminder_service.list_reminders("demo-user")

    assert deleted["deleted_reminder_id"] == created["id"]
    assert reminders == []
    assert runtime.scheduler.removed == [created["id"], created["id"]]


def test_reminder_service_delete_missing_raises_value_error(tmp_path):
    runtime = build_runtime(tmp_path)
    reminder_service = ReminderService(runtime)

    try:
        reminder_service.delete_reminder(999)
        assert False, "Expected ValueError for missing reminder"
    except ValueError as exc:
        assert "Reminder 999 not found" in str(exc)


def test_copilot_service_routes_data_and_reminder_messages(tmp_path):
    runtime = build_runtime(tmp_path)
    service = CopilotService(runtime)

    session_id = "session-1"
    first = service.handle_message("demo-user", session_id, "体温 37.8")
    second = service.handle_message("demo-user", session_id, "每天晚上8点提醒我")

    reminders = runtime.db.list_active_reminders("demo-user")
    records = runtime.db.query_metric_trend("demo-user", "temperature", days=30)

    assert first["current_agent"] == "data_agent"
    assert second["current_agent"] == "reminder_agent"
    assert len(reminders) == 1
    assert len(records) == 1


def test_copilot_service_lists_session_history_with_rule_titles(tmp_path):
    runtime = build_runtime(tmp_path)
    service = CopilotService(runtime)

    service.handle_message("demo-user", "session-a", "体温 37.8")
    service.handle_message("demo-user", "session-b", "每天晚上8点提醒我")

    sessions = service.list_sessions("demo-user")

    assert len(sessions) == 2
    assert sessions[0]["id"] == "session-b"
    assert sessions[0]["display_title"]
    assert sessions[1]["display_title"]


def test_copilot_service_can_delete_single_session(tmp_path):
    runtime = build_runtime(tmp_path)
    service = CopilotService(runtime)

    service.handle_message("demo-user", "session-a", "体温 37.8")
    service.handle_message("demo-user", "session-b", "每天晚上8点提醒我")

    service.delete_session("demo-user", "session-a")

    sessions = service.list_sessions("demo-user")
    messages = service.get_messages("demo-user", "session-a")

    assert [item["id"] for item in sessions] == ["session-b"]
    assert messages == []


def test_copilot_service_can_clear_all_sessions(tmp_path):
    runtime = build_runtime(tmp_path)
    service = CopilotService(runtime)

    service.handle_message("demo-user", "session-a", "体温 37.8")
    service.handle_message("demo-user", "session-b", "每天晚上8点提醒我")

    service.clear_sessions("demo-user")

    assert service.list_sessions("demo-user") == []


def test_copilot_service_general_chat_uses_general_chat_agent(tmp_path):
    db = DBClient(database_url=f"sqlite:///{tmp_path / 'test_general.db'}")
    db.init_tables()

    class GeneralParser:
        def parse(self, message: str):
            return {
                "intent": "general_chat",
                "metrics": [],
                "schedule": {},
                "memory_facts": [],
                "symptoms": [],
                "drugs": [],
            }

    class GeneralPlanner:
        def run(self, user_id: str, session_id: str, message: str, parsed: dict):
            return {"route": "planner", "need_memory_write": False, "risk_level": "low"}

        def build_general_chat(self, message: str, parsed: dict, profile: dict, session_ctx: list[dict]):
            return {
                "answer": "我当前只能解决健康问题。你可以咨询症状、药物、健康记录和提醒。",
                "current_agent": "general_chat_agent",
                "risk_level": "low",
                "citations": [],
                "data": {"intent": "general_chat"},
            }

    runtime = SimpleNamespace(
        db=db,
        parser=GeneralParser(),
        planner=GeneralPlanner(),
        data_agent=FakeDataAgent(db),
        reminder_agent=FakeReminderAgent(db),
        symptom_agent=None,
        drug_agent=None,
        memory=FakeMemory(),
        scheduler=FakeScheduler(),
        tracer=SimpleNamespace(log_event=lambda *args, **kwargs: None),
    )

    service = CopilotService(runtime)
    result = service.handle_message("demo-user", "general-session", "帮我写个旅游攻略")

    assert result["current_agent"] == "general_chat_agent"
    assert "只能解决健康问题" in result["answer"]


def test_copilot_service_stream_message_emits_ordered_events(tmp_path):
    runtime = build_runtime(tmp_path)
    service = CopilotService(runtime)

    events = list(service.stream_message("demo-user", "stream-session", "体温 37.8"))

    event_types = [item["type"] for item in events]

    assert event_types[0] == "user_echo"
    assert "status" in event_types
    assert "agent" in event_types
    assert "tool" in event_types
    assert "assistant_delta" in event_types
    assert event_types[-2:] == ["assistant_done", "done"]
    assert any(item.get("agent") == "data_agent" for item in events if item["type"] == "agent")


def test_copilot_service_stream_message_persists_final_answer(tmp_path):
    runtime = build_runtime(tmp_path)
    service = CopilotService(runtime)

    list(service.stream_message("demo-user", "stream-session", "每天晚上8点提醒我"))
    messages = service.get_messages("demo-user", "stream-session")

    assert messages[-2]["role"] == "user"
    assert messages[-1]["role"] == "assistant"
    assert messages[-1]["content"] == "已创建提醒"
