from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app


class FakeCopilotService:
    def __init__(self):
        self.messages = [{"role": "assistant", "content": "你好，我是健康助手。"}]
        self.sessions = [
            {"id": "session-current", "display_title": "当前会话", "started_at": "2026-03-29T10:00:00", "status": "active"},
            {"id": "session-older", "display_title": "昨晚体温记录", "started_at": "2026-03-28T21:00:00", "status": "active"},
        ]

    def get_messages(self, user_id: str, session_id: str):
        return self.messages

    def list_sessions(self, user_id: str):
        return self.sessions

    def handle_message(self, user_id: str, session_id: str, message: str):
        self.messages.append({"role": "user", "content": message})
        return {
            "answer": "已收到",
            "current_agent": "planner",
            "risk_level": "low",
            "citations": [],
            "data": {},
            "session_id": session_id,
        }

    def stream_message(self, user_id: str, session_id: str, message: str):
        self.messages.append({"role": "user", "content": message})
        yield {"type": "user_echo", "session_id": session_id, "text": message}
        yield {"type": "status", "session_id": session_id, "text": "正在分析问题"}
        yield {"type": "agent", "session_id": session_id, "agent": "planner", "text": "planner"}
        yield {"type": "tool", "session_id": session_id, "tool": "parser", "text": "解析用户输入"}
        yield {"type": "assistant_delta", "session_id": session_id, "text": "已"}
        yield {"type": "assistant_delta", "session_id": session_id, "text": "收到"}
        yield {"type": "assistant_done", "session_id": session_id, "text": "已收到"}
        yield {"type": "done", "session_id": session_id}

    def delete_session(self, user_id: str, session_id: str):
        self.sessions = [item for item in self.sessions if item["id"] != session_id]
        return {"deleted_session_id": session_id}

    def clear_sessions(self, user_id: str):
        self.sessions = []
        return {"cleared": True}


class FakeProfileService:
    def __init__(self):
        self.last_payload = None

    def get_profile(self, user_id: str, trend_window: str = "7d"):
        return {
            "user_id": user_id,
            "basic_info": {"name": "演示用户", "age": "32", "height_cm": "168", "weight_kg": "54.5", "blood_type": "A Rh+"},
            "allergies": ["青霉素"],
            "medical_history": ["慢性胃炎"],
            "trend_window": trend_window,
            "trend_summary": [
                {
                    "metric_type": "temperature",
                    "metric_label": "体温",
                    "latest_value": 37.2,
                    "baseline_value": 36.8,
                    "delta_percent": 0.11,
                    "direction": "up",
                    "sample_count": 5,
                    "has_baseline": True,
                    "unit": "C",
                }
            ],
            "anomaly_alerts": [
                {
                    "metric_type": "temperature",
                    "metric_label": "体温",
                    "latest_value": 38.5,
                    "baseline_value": 36.8,
                    "delta_percent": 0.46,
                    "level": "warning",
                    "reason": "医学边界异常：超出正常范围",
                    "source_scope": "window",
                }
            ],
            "stats": {"record_count": 0, "reminder_count": 1},
        }

    def update_profile(self, user_id: str, payload: dict):
        self.last_payload = payload
        result = self.get_profile(user_id)
        result["basic_info"].update(payload)
        result["allergies"] = payload.get("allergies", result["allergies"])
        result["medical_history"] = payload.get("medical_history", result["medical_history"])
        result["long_term_medications"] = payload.get("long_term_medications", [])
        return result


class FakeRecordService:
    def __init__(self):
        self.records = [
            {
                "id": 1,
                "metric_type": "temperature",
                "metric_label": "体温",
                "metric_value": "36.8",
                "unit": "C",
                "recorded_at": "2026-03-29T09:00:00",
            }
        ]

    def list_records(self, user_id: str, limit: int = 20, days: int | None = None):
        return self.records[:limit]

    def create_record(self, payload: dict):
        if payload.get("record_type") == "blood_pressure" and "/" not in str(payload.get("value", "")):
            raise ValueError("血压请按“舒张压/收缩压”格式输入，例如 80/120。")
        if payload.get("record_type") == "temperature":
            if float(payload.get("value", 0)) > 45:
                raise ValueError("体温超出合理范围")
        recorded_at = str(payload.get("recorded_at") or "").strip()
        if recorded_at:
            if datetime.fromisoformat(recorded_at) > datetime.now() + timedelta(minutes=5):
                raise ValueError("记录时间不能晚于当前时间")
        return {"record": {"metric_type": payload["record_type"], "metric_label": "体温", "metric_value": payload["value"], "unit": "C"}}

    def delete_record(self, user_id: str, record_id: int):
        for item in self.records:
            if item["id"] == record_id:
                self.records = [row for row in self.records if row["id"] != record_id]
                return {"deleted_record_id": record_id}
        raise ValueError(f"Record {record_id} not found")

    def clear_records(self, user_id: str):
        count = len(self.records)
        self.records = []
        return {"cleared": True, "deleted_count": count}


class FakeReminderService:
    def __init__(self):
        self.reminders = [
            {
                "id": 1,
                "target_name": "服药提醒",
                "status": "active",
                "local_time": "20:00",
                "metadata": {"content": "晚上吃药"},
            }
        ]

    def list_reminders(self, user_id: str):
        return [item for item in self.reminders if item["status"] != "deleted"]

    def create_reminder(self, payload: dict):
        created = {"id": len(self.reminders) + 1, "target_name": payload["title"], "status": "active", "local_time": payload.get("schedule_time", ""), "metadata": {"content": payload.get("content", "")}}
        self.reminders.insert(0, created)
        return created

    def toggle_reminder(self, reminder_id: int, enabled: bool):
        for item in self.reminders:
            if item["id"] == reminder_id and item["status"] != "deleted":
                item["status"] = "active" if enabled else "paused"
                return {"id": reminder_id, "status": item["status"]}
        raise ValueError(f"Reminder {reminder_id} not found")

    def delete_reminder(self, reminder_id: int):
        for item in self.reminders:
            if item["id"] == reminder_id and item["status"] != "deleted":
                item["status"] = "deleted"
                return {"deleted_reminder_id": reminder_id}
        raise ValueError(f"Reminder {reminder_id} not found")


def build_client():
    profile_service = FakeProfileService()
    reminder_service = FakeReminderService()
    app = create_app(
        {
            "copilot": FakeCopilotService(),
            "profile": profile_service,
            "record": FakeRecordService(),
            "reminder": reminder_service,
        }
    )
    return TestClient(app)


def test_page_routes_render_successfully():
    client = build_client()

    for path in ("/copilot", "/profile", "/records", "/reminders"):
        response = client.get(path)
        assert response.status_code == 200
        assert "Health Copilot" in response.text


def test_copilot_page_has_new_session_entry():
    client = build_client()

    response = client.get("/copilot")

    assert response.status_code == 200
    assert "新建会话" in response.text
    assert "new_session=1" in response.text
    assert "历史会话" in response.text
    assert "昨晚体温记录" in response.text
    assert "清空全部" in response.text
    assert "删除" in response.text


def test_copilot_page_contains_streaming_chat_hooks():
    client = build_client()

    response = client.get("/copilot")

    assert response.status_code == 200
    assert 'data-chat-feed' in response.text
    assert 'data-copilot-form' in response.text
    assert 'data-stream-endpoint="/api/copilot/message/stream"' in response.text
    assert 'data-process-summary' in response.text
    assert 'data-process-log' in response.text


def test_copilot_without_session_falls_back_to_latest_session():
    client = build_client()

    response = client.get("/copilot", params={"user_id": "demo-user"})

    assert response.status_code == 200
    assert "session-current" in response.text


def test_copilot_new_session_only_when_new_session_param_is_set():
    client = build_client()

    response = client.get(
        "/copilot",
        params={"user_id": "demo-user", "session_id": "session-new", "new_session": "1"},
    )

    assert response.status_code == 200
    assert "session-new" in response.text


def test_navigation_links_preserve_session_context():
    client = build_client()

    response = client.get("/profile", params={"user_id": "demo-user", "session_id": "session-current"})

    assert response.status_code == 200
    assert '/copilot?user_id=demo-user&amp;session_id=session-current' in response.text
    assert '/records?user_id=demo-user&amp;session_id=session-current' in response.text
    assert '/reminders?user_id=demo-user&amp;session_id=session-current' in response.text


def test_chat_delete_endpoints_work():
    client = build_client()

    delete_response = client.post("/api/copilot/session/session-older/delete", json={"user_id": "demo-user"})
    clear_response = client.post("/api/copilot/sessions/clear", json={"user_id": "demo-user"})

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_session_id"] == "session-older"
    assert clear_response.status_code == 200
    assert clear_response.json()["cleared"] is True


def test_copilot_stream_api_returns_sse_events():
    client = build_client()

    with client.stream(
        "POST",
        "/api/copilot/message/stream",
        json={"user_id": "demo-user", "session_id": "session-current", "message": "你好"},
    ) as response:
        body = "".join(chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk for chunk in response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert 'event: user_echo' in body
    assert 'event: assistant_done' in body
    assert 'event: done' in body


def test_records_page_uses_chinese_label_and_no_manual_unit_input():
    client = build_client()

    response = client.get("/records")

    assert response.status_code == 200
    assert "体温" in response.text
    assert 'name="unit"' not in response.text
    assert "最近7天记录" in response.text
    assert "清除全部" in response.text
    assert "删除" in response.text
    assert "例如 80/120（舒张压/收缩压）" in response.text
    assert "data-record-scroll" in response.text


def test_api_routes_support_records_and_profile():
    client = build_client()

    record_response = client.post(
        "/api/records",
        json={
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.8",
            "unit": "C",
            "recorded_at": "2026-03-29T09:00:00",
            "note": "test",
        },
    )
    profile_response = client.get("/api/profile", params={"user_id": "demo-user"})

    assert record_response.status_code == 200
    assert record_response.json()["record"]["metric_type"] == "temperature"
    assert profile_response.status_code == 200
    assert profile_response.json()["basic_info"]["name"] == "演示用户"


def test_records_api_supports_delete_and_clear():
    client = build_client()

    delete_response = client.post("/api/records/1/delete", json={"user_id": "demo-user"})
    clear_response = client.post("/api/records/clear", json={"user_id": "demo-user"})
    clear_alias_response = client.post("/api/records/clear-all", json={"user_id": "demo-user"})

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_record_id"] == 1
    assert clear_response.status_code == 200
    assert clear_response.json()["cleared"] is True
    assert clear_alias_response.status_code == 200


def test_records_api_delete_nonexistent_returns_404():
    client = build_client()

    response = client.post("/api/records/999/delete", json={"user_id": "demo-user"})

    assert response.status_code == 404


def test_records_api_rejects_absurd_or_invalid_values():
    client = build_client()

    absurd_response = client.post(
        "/api/records",
        json={
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "99",
            "recorded_at": "2026-03-29T09:00:00",
            "note": "",
        },
    )
    bp_response = client.post(
        "/api/records",
        json={
            "user_id": "demo-user",
            "record_type": "blood_pressure",
            "value": "120",
            "recorded_at": "2026-03-29T09:00:00",
            "note": "",
        },
    )

    assert absurd_response.status_code == 422
    assert bp_response.status_code == 422


def test_records_api_rejects_future_recorded_time():
    client = build_client()
    future_time = (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds")
    response = client.post(
        "/api/records",
        json={
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.7",
            "recorded_at": future_time,
            "note": "",
        },
    )
    assert response.status_code == 422


def test_profile_page_contains_edit_form():
    client = build_client()

    response = client.get("/profile")

    assert response.status_code == 200
    assert "编辑档案" in response.text
    assert "支持直接编辑基础健康档案，保存后自动刷新数据。" not in response.text
    assert 'data-api-form="profile"' in response.text
    assert 'name="display_name"' in response.text
    assert 'name="allergies"' in response.text
    assert 'name="medical_history"' in response.text
    assert 'name="long_term_medications"' in response.text
    assert 'data-profile-name' in response.text
    assert 'data-profile-allergies-list' in response.text
    assert "趋势摘要" in response.text
    assert "异常提示" in response.text
    assert "近期健康记录" not in response.text
    assert "近7天" in response.text
    assert "近30天" in response.text
    assert "trend_window=30d" in response.text


def test_profile_page_supports_trend_window_switch():
    client = build_client()

    response = client.get("/profile", params={"user_id": "demo-user", "trend_window": "30d"})

    assert response.status_code == 200
    assert "近30天" in response.text
    assert "trend_window=7d" in response.text
    assert 'aria-current="true"' in response.text
    assert "医学边界异常" in response.text


def test_profile_api_accepts_comma_separated_list_fields():
    profile_service = FakeProfileService()
    app = create_app(
        {
            "copilot": FakeCopilotService(),
            "profile": profile_service,
            "record": FakeRecordService(),
            "reminder": FakeReminderService(),
        }
    )
    client = TestClient(app)

    response = client.post(
        "/api/profile",
        json={
            "user_id": "demo-user",
            "display_name": "新用户",
            "allergies": "青霉素, 花粉",
            "medical_history": "慢性胃炎，鼻炎",
            "long_term_medications": "维生素D",
        },
    )

    assert response.status_code == 200
    assert profile_service.last_payload is not None
    assert profile_service.last_payload["allergies"] == ["青霉素", "花粉"]
    assert profile_service.last_payload["medical_history"] == ["慢性胃炎", "鼻炎"]
    assert profile_service.last_payload["long_term_medications"] == ["维生素D"]


def test_reminders_page_contains_toggle_controls():
    client = build_client()

    response = client.get("/reminders")

    assert response.status_code == 200
    assert "状态" in response.text
    assert "暂停" in response.text
    assert 'data-toggle-reminder' in response.text
    assert 'data-reminder-status' in response.text
    assert 'data-delete-reminder' in response.text
    assert 'data-reminder-card' in response.text
    assert 'data-reminder-list' in response.text
    assert 'data-reminder-empty-state-template' in response.text


def test_base_template_uses_versioned_js_asset():
    client = build_client()

    response = client.get("/profile")

    assert response.status_code == 200
    assert '/static/js/app.js?v=' in response.text
    assert 'data-app-version="' in response.text


def test_toggle_reminder_accepts_false_string_value():
    client = build_client()

    response = client.post("/api/reminders/1/toggle", json={"enabled": "false"})

    assert response.status_code == 200
    assert response.json()["status"] == "paused"


def test_reminders_api_supports_delete():
    client = build_client()

    response = client.post("/api/reminders/1/delete")

    assert response.status_code == 200
    assert response.json()["deleted_reminder_id"] == 1


def test_reminders_api_delete_nonexistent_returns_404():
    client = build_client()

    response = client.post("/api/reminders/999/delete")

    assert response.status_code == 404
