from __future__ import annotations

from statistics import median
from typing import Any

from health_agent.schemas.memory_schema import UserProfilePayload
from health_agent.repositories.profile_repository import ProfileRepository
from health_agent.repositories.record_repository import RecordRepository
from health_agent.repositories.reminder_repository import ReminderRepository
from health_agent.services.record_service import METRIC_META


DEFAULT_PROFILE = {
    "display_name": "演示用户",
    "age_range": "32",
    "gender": "女",
    "height_cm": "168",
    "weight_kg": "54.5",
    "blood_type": "A Rh+",
    "allergies": ["青霉素"],
    "chronic_diseases": ["慢性胃炎"],
    "long_term_medications": [],
    "timezone": "Asia/Shanghai",
    "profile_summary": "用于产品演示的默认健康档案。",
}


class ProfileService:
    CORE_TREND_METRICS = ("temperature", "blood_pressure", "blood_glucose", "heart_rate")
    MEDICAL_RANGES = {
        "temperature": (36.1, 37.2),
        "heart_rate": (60.0, 100.0),
        "blood_glucose": (3.9, 7.8),
        "blood_pressure_systolic": (90.0, 139.0),
        "blood_pressure_diastolic": (60.0, 89.0),
    }

    def __init__(self, runtime):
        self.runtime = runtime
        self.profiles = ProfileRepository(runtime.db)
        self.records = RecordRepository(runtime.db)
        self.reminders = ReminderRepository(runtime.db)

    def ensure_profile(self, user_id: str) -> dict:
        profile = self.profiles.get_profile(user_id)
        if profile is None:
            payload = UserProfilePayload(user_id=user_id, **DEFAULT_PROFILE)
            self.profiles.save_profile(payload)
            profile = self.profiles.get_profile(user_id)
        return profile

    def get_profile(self, user_id: str, trend_window: str = "7d") -> dict:
        profile = self.ensure_profile(user_id)
        recent_records = self.records.list_records(user_id, limit=6)
        for record in recent_records:
            meta = METRIC_META.get(record["metric_type"], {"label": record["metric_type"], "unit": record.get("unit", "")})
            record["metric_label"] = meta["label"]
            if not record.get("unit"):
                record["unit"] = meta["unit"]
        resolved_window = trend_window if trend_window in {"7d", "30d"} else "7d"
        trend_days = 7 if resolved_window == "7d" else 30
        trend_summary, anomaly_alerts = self._build_trend_summary(user_id, trend_days)
        reminders = self.reminders.list_reminders(user_id)
        return {
            "user_id": user_id,
            "trend_window": resolved_window,
            "basic_info": {
                "name": profile.get("display_name") or "演示用户",
                "age": profile.get("age_range") or "-",
                "height_cm": profile.get("height_cm") or "-",
                "weight_kg": profile.get("weight_kg") or "-",
                "blood_type": profile.get("blood_type") or "-",
                "gender": profile.get("gender") or "-",
            },
            "allergies": profile.get("allergies", []),
            "medical_history": profile.get("chronic_diseases", []),
            "long_term_medications": profile.get("long_term_medications", []),
            "summary": profile.get("profile_summary", ""),
            "recent_records": recent_records,
            "trend_summary": trend_summary,
            "anomaly_alerts": anomaly_alerts,
            "stats": {
                "record_count": len(self.records.list_records(user_id, limit=200)),
                "reminder_count": len(reminders),
            },
        }

    def update_profile(self, user_id: str, payload: dict) -> dict:
        current = self.ensure_profile(user_id)
        merged = {
            "user_id": user_id,
            "display_name": payload.get("display_name", current.get("display_name")),
            "age_range": payload.get("age_range", current.get("age_range")),
            "gender": payload.get("gender", current.get("gender")),
            "height_cm": payload.get("height_cm", current.get("height_cm")),
            "weight_kg": payload.get("weight_kg", current.get("weight_kg")),
            "blood_type": payload.get("blood_type", current.get("blood_type")),
            "chronic_diseases": payload.get("medical_history", current.get("chronic_diseases", [])),
            "allergies": payload.get("allergies", current.get("allergies", [])),
            "long_term_medications": payload.get(
                "long_term_medications", current.get("long_term_medications", [])
            ),
            "timezone": payload.get("timezone", current.get("timezone")),
            "profile_summary": payload.get("profile_summary", current.get("profile_summary", "")),
        }
        self.profiles.save_profile(UserProfilePayload(**merged))
        return self.get_profile(user_id, trend_window="7d")

    def _build_trend_summary(self, user_id: str, days: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        summary: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []
        for metric_type in self.CORE_TREND_METRICS:
            rows = self.runtime.db.query_metric_trend(user_id, metric_type, days=days)
            sample_count = len(rows)
            meta = METRIC_META.get(metric_type, {"label": metric_type, "unit": ""})
            if sample_count == 0:
                latest_any = self.records.latest_record_by_type(user_id, metric_type)
                if latest_any:
                    medical_alert = self._build_medical_alert(metric_type, meta["label"], latest_any, source_scope="fallback")
                    if medical_alert:
                        alerts.append(medical_alert)
                continue

            latest_value = self._to_number(rows[0].get("metric_value"))
            baseline_value = None
            has_baseline = False
            delta_percent = None
            direction = "flat"
            if sample_count >= 4 and latest_value is not None:
                history_values = [
                    self._to_number(item.get("metric_value"))
                    for item in rows[1:]
                ]
                clean_history = [value for value in history_values if value is not None]
                if len(clean_history) >= 3:
                    baseline_value = median(clean_history)
                    if baseline_value not in (None, 0):
                        has_baseline = True
                        delta_percent = (latest_value - baseline_value) / baseline_value
                        if delta_percent > 0.01:
                            direction = "up"
                        elif delta_percent < -0.01:
                            direction = "down"
                        else:
                            direction = "flat"

            item = {
                "metric_type": metric_type,
                "metric_label": meta["label"],
                "latest_value": latest_value,
                "baseline_value": baseline_value,
                "delta_percent": delta_percent,
                "direction": direction,
                "sample_count": sample_count,
                "has_baseline": has_baseline,
                "unit": meta.get("unit", ""),
            }
            summary.append(item)
            if has_baseline and delta_percent is not None and abs(delta_percent) >= 0.2:
                alerts.append(
                    {
                        "metric_type": metric_type,
                        "metric_label": meta["label"],
                        "latest_value": latest_value,
                        "baseline_value": baseline_value,
                        "delta_percent": delta_percent,
                        "level": "warning",
                        "reason": "个人基线异常：相对个人基线波动超过20%",
                        "source_scope": "window",
                    }
                )
            medical_alert = self._build_medical_alert(metric_type, meta["label"], rows[0], source_scope="window")
            if medical_alert:
                alerts.append(medical_alert)
        return summary, alerts

    def _to_number(self, value: Any) -> float | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        if "/" in text:
            text = text.split("/", 1)[0].strip()
        try:
            return float(text)
        except ValueError:
            return None

    def _parse_blood_pressure(self, value: Any) -> tuple[float | None, float | None]:
        text = str(value or "").strip()
        if not text:
            return None, None
        if "/" not in text:
            return self._to_number(text), None
        left, right = text.split("/", 1)
        return self._to_number(left), self._to_number(right)

    def _build_medical_alert(
        self,
        metric_type: str,
        metric_label: str,
        latest_row: dict[str, Any],
        source_scope: str,
    ) -> dict[str, Any] | None:
        raw_value = latest_row.get("metric_value")
        latest_value = self._to_number(raw_value)
        out_of_range = False
        reason_detail = ""

        if metric_type == "blood_pressure":
            systolic, diastolic = self._parse_blood_pressure(raw_value)
            sys_min, sys_max = self.MEDICAL_RANGES["blood_pressure_systolic"]
            dia_min, dia_max = self.MEDICAL_RANGES["blood_pressure_diastolic"]
            if systolic is not None and not (sys_min <= systolic <= sys_max):
                out_of_range = True
                reason_detail = f"收缩压超出 {int(sys_min)}-{int(sys_max)}"
            if diastolic is not None and not (dia_min <= diastolic <= dia_max):
                out_of_range = True
                reason_detail = reason_detail or f"舒张压超出 {int(dia_min)}-{int(dia_max)}"
            latest_value = systolic
        else:
            bounds = self.MEDICAL_RANGES.get(metric_type)
            if bounds and latest_value is not None:
                low, high = bounds
                if not (low <= latest_value <= high):
                    out_of_range = True
                    reason_detail = f"超出正常范围 {low}-{high}"

        if not out_of_range:
            return None

        suffix = "（非当前窗口）" if source_scope == "fallback" else ""
        return {
            "metric_type": metric_type,
            "metric_label": metric_label,
            "latest_value": latest_value,
            "baseline_value": None,
            "delta_percent": None,
            "level": "warning",
            "reason": f"医学边界异常：{reason_detail}{suffix}",
            "source_scope": source_scope,
        }
