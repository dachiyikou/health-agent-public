from __future__ import annotations

from langchain_openai import ChatOpenAI

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, DASHSCOPE_CHAT_MODEL, MAX_FOLLOWUP_QUESTIONS, PROMPTS_DIR
from schemas.agent_schema import SymptomResult
from tools.rag import RAGService


def _load_prompt() -> str:
    path = PROMPTS_DIR / "symptom_prompt.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是症状分析助手。结合检索到的知识给出保守、清晰的建议，并提醒用户就医边界。"


class SymptomAgent:
    def __init__(self, rag: RAGService):
        self.rag = rag
        self.llm = ChatOpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            model=DASHSCOPE_CHAT_MODEL,
            temperature=0.2,
        )
        self.prompt = _load_prompt()

    def _build_followups(self, symptoms: list[str]) -> list[str]:
        default_questions = [
            "这些症状持续了多久？",
            "有没有伴随高热、呼吸困难或胸痛？",
            "最近是否服用了什么药物？",
        ]
        if "腹痛" in symptoms:
            default_questions[1] = "腹痛的位置、强度和持续时间是怎样的？"
        if "咳嗽" in symptoms:
            default_questions[1] = "咳嗽时有没有痰、胸闷或呼吸困难？"
        return default_questions[:MAX_FOLLOWUP_QUESTIONS]

    def _triage(self, message: str, risk_level: str) -> str:
        if risk_level == "high":
            return "emergency"
        if "39" in message or "40" in message:
            return "urgent"
        return "outpatient" if risk_level == "medium" else "self_care"

    def run(self, message: str, parsed: dict, profile: dict, session_ctx: list[dict], risk_level: str) -> dict:
        rag_result = self.rag.retrieve(message, domain="symptom")
        prompt = (
            f"{self.prompt}\n\n"
            f"用户画像：{profile}\n"
            f"最近会话：{session_ctx}\n"
            f"症状：{parsed.get('symptoms', [])}\n"
            f"知识上下文：{rag_result['context']}\n"
            f"原始用户输入：{message}\n\n"
            "请输出简洁中文建议，包含风险提醒、居家观察建议、何时线下就医。"
        )
        response = self.llm.invoke(prompt)
        result = SymptomResult(
            answer=f"{response.content.strip()}\n\n免责声明：以上内容仅供健康信息参考，不能替代医生诊疗。",
            current_agent="symptom_agent",
            risk_level=risk_level,
            citations=rag_result["citations"],
            data={"chief_complaint": parsed.get("symptoms", [])},
            follow_up_questions=self._build_followups(parsed.get("symptoms", [])),
            triage_level=self._triage(message, risk_level),
        )
        return result.model_dump()
