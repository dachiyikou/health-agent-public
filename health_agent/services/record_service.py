from __future__ import annotations

from datetime import datetime, timedelta

from schemas.record_schema import DataRecordPayload, ManualRecordPayload
from health_agent.repositories.record_repository import RecordRepository


METRIC_META = {
    "temperature": {"label": "体温", "unit": "C"},
    "blood_pressure": {"label": "血压", "unit": "mmHg"},
    "blood_glucose": {"label": "血糖", "unit": "mmol/L"},
    "heart_rate": {"label": "心率", "unit": "bpm"},
    "weight": {"label": "体重", "unit": "kg"},
    "spo2": {"label": "血氧", "unit": "%"},
}


class RecordService:
    VALUE_RANGES = {
        "temperature": (30.0, 45.0),
        "blood_glucose": (1.5, 35.0),
        "heart_rate": (25.0, 260.0),
        "weight": (2.0, 500.0),
        "spo2": (50.0, 100.0),
    }

    def __init__(self, runtime):
        self.runtime = runtime
        self.records = RecordRepository(runtime.db)

    def create_record(self, payload: dict) -> dict:
        request = ManualRecordPayload(**payload)
        meta = METRIC_META.get(request.record_type, {"label": request.record_type, "unit": request.unit or ""})
        resolved_unit = request.unit or meta["unit"]
        normalized_value = self._validate_value(request.record_type, request.value)
        normalized_recorded_at = self._validate_recorded_at(request.recorded_at)
        record = DataRecordPayload(
            user_id=request.user_id,
            metric_type=request.record_type,
            metric_value=normalized_value,
            unit=resolved_unit,
            recorded_at=normalized_recorded_at,
            source="manual",
            note=request.note,
        )
        record_id = self.records.create_record(record)
        created = {
            "id": record_id,
            "user_id": record.user_id,
            "metric_type": record.metric_type,
            "metric_label": meta["label"],
            "metric_value": record.metric_value,
            "unit": record.unit,
            "recorded_at": record.recorded_at,
            "source": record.source,
            "note": record.note,
        }
        return {"record_id": record_id, "record": created}

    def list_records(self, user_id: str, limit: int = 20, days: int | None = None) -> list[dict]:
        if days is not None:
            items = self.records.list_recent_records(user_id, days=days, limit=limit)
        else:
            items = self.records.list_records(user_id, limit=limit)
        for item in items:
            meta = METRIC_META.get(item["metric_type"], {"label": item["metric_type"], "unit": item.get("unit", "")})
            item["metric_label"] = meta["label"]
            if not item.get("unit"):
                item["unit"] = meta["unit"]
        return items

    def delete_record(self, user_id: str, record_id: int) -> dict:
        deleted = self.records.delete_record(user_id, record_id)
        if not deleted:
            raise ValueError(f"Record {record_id} not found")
        return {"deleted_record_id": record_id}

    def clear_records(self, user_id: str) -> dict:
        count = self.records.clear_records(user_id)
        return {"cleared": True, "deleted_count": count}

    def _validate_value(self, record_type: str, value: str) -> str:
        raw = str(value or "").strip()
        if not raw:
            raise ValueError("记录数值不能为空")

        if record_type == "blood_pressure":
            if "/" not in raw:
                raise ValueError("血压必须按“舒张压/收缩压”格式输入，例如 80/120")
            dia_text, sys_text = [part.strip() for part in raw.split("/", 1)]
            try:
                diastolic = int(dia_text)
                systolic = int(sys_text)
            except ValueError as exc:
                raise ValueError("血压必须是整数，格式如 80/120（舒张压/收缩压）") from exc
            if not (40 <= diastolic <= 150 and 70 <= systolic <= 260 and diastolic < systolic):
                raise ValueError("血压数值异常，请按“舒张压/收缩压”输入合理范围")
            return f"{diastolic}/{systolic}"

        try:
            number = float(raw)
        except ValueError as exc:
            raise ValueError("记录数值必须是数字") from exc

        low_high = self.VALUE_RANGES.get(record_type)
        if low_high is not None:
            low, high = low_high
            if number < low or number > high:
                unit = METRIC_META.get(record_type, {}).get("unit", "")
                raise ValueError(
                    f"{METRIC_META.get(record_type, {}).get('label', record_type)}超出合理范围 {low:g}-{high:g}{unit}"
                )
        return raw

    def _validate_recorded_at(self, recorded_at: str | None) -> str | None:
        if recorded_at is None:
            return None
        text = str(recorded_at).strip()
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError("记录时间格式错误，请使用 YYYY-MM-DDTHH:MM 或 YYYY-MM-DDTHH:MM:SS") from exc
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        if parsed > datetime.now() + timedelta(minutes=5):
            raise ValueError("记录时间不能晚于当前时间")
        return text
