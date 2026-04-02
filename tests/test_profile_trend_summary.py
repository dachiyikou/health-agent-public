from datetime import datetime, timedelta
from types import SimpleNamespace

from health_agent.services.profile_service import ProfileService
from health_agent.services.record_service import RecordService
from health_agent.tools.db import DBClient


class _FakeScheduler:
    def sync_job(self, reminder: dict):
        return None

    def remove_job(self, reminder_id):
        return None


def _build_runtime(tmp_path):
    db = DBClient(database_url=f"sqlite:///{tmp_path / 'trend.db'}")
    db.init_tables()
    return SimpleNamespace(db=db, scheduler=_FakeScheduler())


def _iso_days_ago(days: int) -> str:
    return (datetime.utcnow() - timedelta(days=days)).replace(microsecond=0).isoformat()


def test_profile_trend_summary_marks_insufficient_baseline(tmp_path):
    runtime = _build_runtime(tmp_path)
    record_service = RecordService(runtime)
    profile_service = ProfileService(runtime)

    for idx, value in enumerate(("36.7", "36.8", "36.9")):
        record_service.create_record(
            {
                "user_id": "demo-user",
                "record_type": "temperature",
                "value": value,
                "unit": "C",
                "recorded_at": _iso_days_ago(idx + 1),
                "note": "",
            }
        )

    profile = profile_service.get_profile("demo-user", trend_window="7d")
    temp = next(item for item in profile["trend_summary"] if item["metric_type"] == "temperature")

    assert profile["trend_window"] == "7d"
    assert temp["sample_count"] == 3
    assert temp["has_baseline"] is False
    assert profile["anomaly_alerts"] == []


def test_profile_trend_summary_detects_baseline_deviation(tmp_path):
    runtime = _build_runtime(tmp_path)
    record_service = RecordService(runtime)
    profile_service = ProfileService(runtime)

    values = ("44.0", "36.6", "36.6", "36.5")
    for idx, value in enumerate(values):
        record_service.create_record(
            {
                "user_id": "demo-user",
                "record_type": "temperature",
                "value": value,
                "unit": "C",
                "recorded_at": _iso_days_ago(idx + 1),
                "note": "",
            }
        )

    profile = profile_service.get_profile("demo-user", trend_window="7d")
    temp = next(item for item in profile["trend_summary"] if item["metric_type"] == "temperature")

    assert temp["sample_count"] == 4
    assert temp["has_baseline"] is True
    assert temp["delta_percent"] >= 0.2
    assert len(profile["anomaly_alerts"]) >= 1
    assert any(item["metric_type"] == "temperature" and "个人基线异常" in item["reason"] for item in profile["anomaly_alerts"])
    assert any(item["metric_type"] == "temperature" and "医学边界异常" in item["reason"] for item in profile["anomaly_alerts"])


def test_profile_trend_summary_respects_window_selection(tmp_path):
    runtime = _build_runtime(tmp_path)
    record_service = RecordService(runtime)
    profile_service = ProfileService(runtime)

    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "37.0",
            "unit": "C",
            "recorded_at": _iso_days_ago(2),
            "note": "",
        }
    )
    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "36.6",
            "unit": "C",
            "recorded_at": _iso_days_ago(20),
            "note": "",
        }
    )

    p7 = profile_service.get_profile("demo-user", trend_window="7d")
    p30 = profile_service.get_profile("demo-user", trend_window="30d")
    s7 = next(item for item in p7["trend_summary"] if item["metric_type"] == "temperature")
    s30 = next(item for item in p30["trend_summary"] if item["metric_type"] == "temperature")

    assert p7["trend_window"] == "7d"
    assert p30["trend_window"] == "30d"
    assert s7["sample_count"] == 1
    assert s30["sample_count"] == 2


def test_profile_medical_alert_can_trigger_without_baseline(tmp_path):
    runtime = _build_runtime(tmp_path)
    record_service = RecordService(runtime)
    profile_service = ProfileService(runtime)

    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "heart_rate",
            "value": "128",
            "unit": "bpm",
            "recorded_at": _iso_days_ago(1),
            "note": "",
        }
    )

    profile = profile_service.get_profile("demo-user", trend_window="7d")
    assert len(profile["trend_summary"]) == 1
    assert profile["trend_summary"][0]["metric_type"] == "heart_rate"
    assert profile["trend_summary"][0]["has_baseline"] is False
    assert len(profile["anomaly_alerts"]) == 1
    assert "医学边界异常" in profile["anomaly_alerts"][0]["reason"]


def test_profile_empty_window_uses_latest_record_for_medical_alert(tmp_path):
    runtime = _build_runtime(tmp_path)
    record_service = RecordService(runtime)
    profile_service = ProfileService(runtime)

    record_service.create_record(
        {
            "user_id": "demo-user",
            "record_type": "temperature",
            "value": "39.0",
            "unit": "C",
            "recorded_at": _iso_days_ago(20),
            "note": "",
        }
    )

    profile = profile_service.get_profile("demo-user", trend_window="7d")

    assert profile["trend_summary"] == []
    assert len(profile["anomaly_alerts"]) == 1
    assert profile["anomaly_alerts"][0]["metric_type"] == "temperature"
    assert profile["anomaly_alerts"][0]["source_scope"] == "fallback"
