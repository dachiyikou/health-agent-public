from __future__ import annotations

from langchain_openai import ChatOpenAI

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, DASHSCOPE_REASON_MODEL, PROMPTS_DIR
from schemas.agent_schema import DrugResult
from tools.db import DBClient
from tools.rag import RAGService


def _load_prompt() -> str:
    path = PROMPTS_DIR / "drug_prompt.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return "你是药物咨询助手。必须保守回答，不编造药品信息，并始终提醒用户咨询医生或药师。"


class DrugAgent:
    def __init__(self, rag: RAGService, db: DBClient):
        self.rag = rag
        self.db = db
        self.llm = ChatOpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            model=DASHSCOPE_REASON_MODEL,
            temperature=0,
        )
        self.prompt = _load_prompt()

    def _detect_interaction_risk(self, parsed: dict, current_meds: list[dict]) -> str:
        asked_names = {item["name"] for item in parsed.get("drugs", [])}
        current_names = {item["drug_name"] for item in current_meds}
        if asked_names & current_names:
            return "review_existing_medication"
        if len(asked_names) + len(current_names) >= 2:
            return "needs_review"
        return "low"

    def _find_contraindications(self, profile: dict, parsed: dict) -> list[str]:
        contraindications: list[str] = []
        allergies = set(profile.get("allergies", []))
        for drug in parsed.get("drugs", []):
            if drug["name"] in allergies:
                contraindications.append(f"用户记录中对 {drug['name']} 过敏")
        return contraindications

    def run(self, message: str, parsed: dict, profile: dict) -> dict:
        rag_result = self.rag.retrieve(message, domain="drug")
        current_meds = self.db.get_user_medications(profile["user_id"])
        interaction_risk = self._detect_interaction_risk(parsed, current_meds)
        contraindications = self._find_contraindications(profile, parsed)
        prompt = (
            f"{self.prompt}\n\n"
            f"用户档案：{profile}\n"
            f"当前长期用药：{current_meds}\n"
            f"本次识别药物：{parsed.get('drugs', [])}\n"
            f"知识上下文：{rag_result['context']}\n"
            f"用户问题：{message}\n\n"
            "请用中文给出用药说明、常见风险和需要线下确认的点。"
        )
        response = self.llm.invoke(prompt)
        result = DrugResult(
            answer=f"{response.content.strip()}\n\n免责声明：具体用药请以医生或药师意见为准。",
            current_agent="drug_agent",
            risk_level="medium" if contraindications else "low",
            citations=rag_result["citations"],
            data={"drugs": parsed.get("drugs", []), "current_medications": current_meds},
            interaction_risk=interaction_risk,
            contraindications=contraindications,
        )
        return result.model_dump()
