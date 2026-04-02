from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_openai import ChatOpenAI

from config import (
    DASHSCOPE_API_KEY,
    DASHSCOPE_BASE_URL,
    DASHSCOPE_CHAT_MODEL,
    MAX_FOLLOWUP_QUESTIONS,
    PROMPTS_DIR,
)
from schemas.agent_schema import PlannerResult


def _load_prompt(filename: str, fallback: str) -> str:
    path = PROMPTS_DIR / filename
    if path.exists():
        return path.read_text(encoding="utf-8")
    return fallback


class PlannerAgent:
    HIGH_RISK_KEYWORDS = ["胸痛", "呼吸困难", "抽搐", "意识不清", "黑便", "持续高热"]
    HEALTH_CONTEXT_KEYWORDS = [
        "健康",
        "症状",
        "头痛",
        "头疼",
        "頭痛",
        "頭疼",
        "发烧",
        "發燒",
        "咳嗽",
        "腹痛",
        "恶心",
        "頭暈",
        "头晕",
        "血压",
        "血壓",
        "血糖",
        "体温",
        "體溫",
        "心率",
        "体重",
        "體重",
        "血氧",
        "药",
        "藥",
        "用药",
        "用藥",
        "提醒",
        "睡眠",
        "饮食",
        "飲食",
        "运动",
        "運動",
    ]

    def __init__(self) -> None:
        self.prompt = _load_prompt(
            "planner_prompt.md",
            "你是健康助手的路由器，负责判断意图、风险和目标 agent。",
        )
        self.general_chat_llm = ChatOpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            model=DASHSCOPE_CHAT_MODEL,
            temperature=0.2,
        )

    def detect_risk(self, message: str, parsed: dict[str, Any]) -> str:
        if any(keyword in message for keyword in self.HIGH_RISK_KEYWORDS):
            return "high"
        symptoms = parsed.get("symptoms", [])
        if any("体温4" in symptom for symptom in symptoms):
            return "medium"
        if symptoms:
            return "medium"
        return "low"

    def choose_route(self, intent: str) -> str:
        route_map = {
            "symptom_check": "symptom_agent",
            "drug_consult": "drug_agent",
            "data_record": "data_agent",
            "reminder_set": "reminder_agent",
        }
        return route_map.get(intent, "planner")

    def run(self, user_id: str, session_id: str, message: str, parsed: dict[str, Any]) -> dict[str, Any]:
        risk_level = self.detect_risk(message, parsed)
        route = self.choose_route(parsed.get("intent", "general_chat"))
        plan = PlannerResult(
            intent=parsed.get("intent", "general_chat"),
            route=route,
            risk_level=risk_level,
            need_rag=route in {"symptom_agent", "drug_agent"},
            need_memory_write=bool(parsed.get("memory_facts")),
            parsed=parsed,
        )
        return plan.model_dump()

    def build_clarification(self, parsed: dict[str, Any]) -> dict[str, Any]:
        return {
            "answer": (
                "我可以帮你做四类事：症状分析、药物咨询、健康数据记录、提醒设置。"
                "你可以更具体描述一下你的需求。"
            ),
            "citations": [],
            "risk_level": "low",
            "current_agent": "planner",
            "data": {"intent": parsed.get("intent", "general_chat"), "max_followup_questions": MAX_FOLLOWUP_QUESTIONS},
        }

    def _is_health_related(self, message: str, parsed: dict[str, Any]) -> bool:
        if parsed.get("symptoms") or parsed.get("drugs") or parsed.get("metrics") or parsed.get("schedule"):
            return True
        return any(keyword in message for keyword in self.HEALTH_CONTEXT_KEYWORDS)

    def build_general_chat(
        self,
        message: str,
        parsed: dict[str, Any],
        profile: dict[str, Any],
        session_ctx: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self._is_health_related(message, parsed):
            return {
                "answer": "我当前只能解决健康问题。你可以咨询症状、药物、健康记录和提醒。",
                "citations": [],
                "risk_level": "low",
                "current_agent": "general_chat_agent",
                "data": {"intent": parsed.get("intent", "general_chat"), "max_followup_questions": MAX_FOLLOWUP_QUESTIONS},
            }

        prompt = (
            "你是健康助手，只回答健康相关问题。\n"
            f"用户档案：{profile}\n"
            f"最近会话：{session_ctx}\n"
            f"解析结果：{parsed}\n"
            f"用户输入：{message}\n\n"
            "请用简洁中文给出健康建议。若信息不足，提出1-2个关键追问。"
        )
        response = self.general_chat_llm.invoke(prompt)
        answer = (response.content or "").strip()
        if not answer:
            answer = "请再描述一下你的健康问题细节，例如症状、持续时间和严重程度。"
        return {
            "answer": answer,
            "citations": [],
            "risk_level": "low",
            "current_agent": "general_chat_agent",
            "data": {"intent": parsed.get("intent", "general_chat"), "max_followup_questions": MAX_FOLLOWUP_QUESTIONS},
        }
