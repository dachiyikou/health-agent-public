from __future__ import annotations

import re
from datetime import datetime

from langchain_openai import ChatOpenAI

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, DASHSCOPE_CHAT_MODEL


class InputParser:
    HIGH_RISK_KEYWORDS = ["胸痛", "呼吸困难", "抽搐", "意识不清", "黑便", "持续高热"]
    SYMPTOM_KEYWORDS = [
        "发烧",
        "發燒",
        "发热",
        "咳嗽",
        "头痛",
        "頭痛",
        "头疼",
        "頭疼",
        "头晕",
        "頭暈",
        "腹痛",
        "恶心",
        "噁心",
        "呕吐",
        "嘔吐",
        "腹泻",
        "腹瀉",
        "喉咙痛",
        "喉嚨痛",
        "鼻塞",
        "不舒服",
        "不適",
        "难受",
        "難受",
    ]
    DRUG_KEYWORDS = ["布洛芬", "阿莫西林", "头孢", "感冒灵", "退烧药", "止痛药", "青霉素"]
    REMINDER_KEYWORDS = ["提醒", "闹钟", "定时", "每", "每天", "服药时间", "吃药", "服藥"]
    INTENT_LABELS = {"symptom_check", "drug_consult", "data_record", "reminder_set", "general_chat", "non_health"}

    def __init__(self, intent_classifier=None):
        self.intent_classifier = intent_classifier
        self._intent_llm = None

    def parse(self, text: str) -> dict:
        intent = self.parse_intent(text)
        result = {
            "intent": intent,
            "symptoms": self.extract_symptoms(text),
            "drugs": self.extract_drugs(text),
            "metrics": self.extract_metrics(text),
            "schedule": self.parse_schedule(text),
            "time_expressions": self.extract_time_expressions(text),
            "memory_facts": self.extract_memory_facts(text),
            "confidence": self.estimate_confidence(intent, text),
        }
        return result

    def parse_intent(self, text: str) -> str:
        if any(keyword in text for keyword in self.REMINDER_KEYWORDS):
            return "reminder_set"
        if self.extract_metrics(text):
            return "data_record"
        if any(keyword in text for keyword in self.DRUG_KEYWORDS) or "药" in text or "藥" in text:
            return "drug_consult"
        if any(keyword in text for keyword in self.SYMPTOM_KEYWORDS):
            return "symptom_check"
        llm_intent = self._classify_intent_with_llm(text)
        if llm_intent == "non_health":
            return "general_chat"
        return llm_intent

    def extract_symptoms(self, text: str) -> list[str]:
        found = [keyword for keyword in self.SYMPTOM_KEYWORDS if keyword in text]
        temp_match = re.search(r"(\d{2}(?:\.\d)?)\s*度", text)
        if temp_match:
            found.append(f"体温{temp_match.group(1)}度")
        return found

    def extract_drugs(self, text: str) -> list[dict]:
        found = []
        for keyword in self.DRUG_KEYWORDS:
            if keyword in text:
                dosage_match = re.search(rf"{keyword}.*?(\d+\s*(?:mg|ml|片|粒))", text, flags=re.IGNORECASE)
                found.append({"name": keyword, "dosage": dosage_match.group(1) if dosage_match else ""})
        return found

    def extract_metrics(self, text: str) -> list[dict]:
        metrics = []
        for pattern, metric_type, unit in (
            (r"体温[:：]?\s*(\d{2}(?:\.\d)?)", "temperature", "C"),
            (r"血压[:：]?\s*(\d{2,3}/\d{2,3})", "blood_pressure", "mmHg"),
            (r"血糖[:：]?\s*(\d+(?:\.\d+)?)", "blood_glucose", "mmol/L"),
            (r"心率[:：]?\s*(\d{2,3})", "heart_rate", "bpm"),
            (r"体重[:：]?\s*(\d+(?:\.\d+)?)", "weight", "kg"),
            (r"血氧[:：]?\s*(\d{2,3})", "spo2", "%"),
        ):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                metrics.append({"metric_type": metric_type, "metric_value": match.group(1), "unit": unit})
        return metrics

    def parse_schedule(self, text: str) -> dict:
        schedule: dict[str, str] = {}
        time_match = re.search(r"(上午|中午|下午|晚上)?\s*(\d{1,2})[:：点](\d{1,2})?", text)
        if time_match and any(word in text for word in ["提醒", "闹钟", "定时", "服药"]):
            meridiem = time_match.group(1) or ""
            hour = int(time_match.group(2))
            minute = int(time_match.group(3) or "0")
            if meridiem in {"下午", "晚上"} and hour < 12:
                hour += 12
            schedule["local_time"] = f"{hour:02d}:{minute:02d}"
        if "每天" in text:
            schedule["cron_expr"] = "0 0 * * *"
        return schedule

    def extract_time_expressions(self, text: str) -> list[str]:
        return re.findall(r"(今天|明天|后天|每天|每周|上午|中午|下午|晚上)", text)

    def extract_memory_facts(self, text: str) -> list[dict]:
        facts: list[dict] = []
        allergy_match = re.search(r"对(.+?)(过敏)", text)
        if allergy_match:
            value = allergy_match.group(1).strip()
            facts.append(
                {
                    "field": "allergies",
                    "value": value,
                    "content": f"用户对{value}过敏",
                    "importance": 0.95,
                }
            )
        chronic_match = re.search(r"(有|患有)(高血压|糖尿病|哮喘|慢阻肺)", text)
        if chronic_match:
            value = chronic_match.group(2)
            facts.append(
                {
                    "field": "chronic_diseases",
                    "value": value,
                    "content": f"用户有{value}",
                    "importance": 0.9,
                }
            )
        med_match = re.search(r"长期(吃|服用)(.+)", text)
        if med_match:
            value = med_match.group(2).strip()
            facts.append(
                {
                    "field": "long_term_medications",
                    "value": value,
                    "content": f"用户长期用药：{value}",
                    "importance": 0.9,
                }
            )
        timezone_match = re.search(r"(上海|北京|中国|UTC[+-]\d+)", text, flags=re.IGNORECASE)
        if timezone_match and "时区" in text:
            facts.append(
                {
                    "field": "timezone",
                    "value": "Asia/Shanghai" if timezone_match.group(1) in {"上海", "北京", "中国"} else timezone_match.group(1),
                    "content": f"用户时区是{timezone_match.group(1)}",
                    "importance": 0.85,
                }
            )
        return facts

    def estimate_confidence(self, intent: str, text: str) -> float:
        if intent != "general_chat":
            return 0.9
        return 0.6 if len(text.strip()) > 8 else 0.4

    def _classify_intent_with_llm(self, text: str) -> str:
        if self.intent_classifier is not None:
            label = (self.intent_classifier(text) or "").strip()
            return label if label in self.INTENT_LABELS else "general_chat"
        if not DASHSCOPE_API_KEY:
            return "general_chat"
        try:
            if self._intent_llm is None:
                self._intent_llm = ChatOpenAI(
                    api_key=DASHSCOPE_API_KEY,
                    base_url=DASHSCOPE_BASE_URL,
                    model=DASHSCOPE_CHAT_MODEL,
                    temperature=0,
                )
            prompt = (
                "你是健康意图分类器。"
                "请只输出一个标签，不要输出其它内容。"
                "可选标签：symptom_check, drug_consult, data_record, reminder_set, general_chat, non_health。\n"
                f"用户输入：{text}"
            )
            response = self._intent_llm.invoke(prompt)
            label = (response.content or "").strip().split()[0]
            if label in self.INTENT_LABELS:
                return label
        except Exception:
            return "general_chat"
        return "general_chat"
