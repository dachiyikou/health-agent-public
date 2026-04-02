from __future__ import annotations

from langchain_openai import ChatOpenAI

from config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, MEMORY_SUMMARY_MODEL


class SessionSummarizer:
    def __init__(self) -> None:
        self.llm = ChatOpenAI(
            api_key=DASHSCOPE_API_KEY,
            base_url=DASHSCOPE_BASE_URL,
            model=MEMORY_SUMMARY_MODEL,
            temperature=0,
        )

    def summarize_messages(self, messages: list[dict]) -> str:
        if not messages:
            return ""
        transcript = "\n".join(f"{item['role']}: {item['content']}" for item in messages[-12:])
        prompt = (
            "你是健康助手的记忆摘要模块。请用简洁中文总结这段对话中的"
            "稳定健康信息、当前问题、后续待跟进事项。控制在120字内。\n\n"
            f"{transcript}"
        )
        response = self.llm.invoke(prompt)
        return response.content.strip()
