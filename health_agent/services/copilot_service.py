from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

from health_agent.repositories.chat_repository import ChatRepository


class CopilotService:
    def __init__(self, runtime):
        self.runtime = runtime
        self.chats = ChatRepository(runtime.db)

    def handle_message(self, user_id: str, session_id: str, message: str) -> dict:
        result, parsed, _, _ = self._execute_message(user_id, session_id, message)
        result["session_id"] = session_id
        result["user_id"] = user_id
        result["parsed"] = parsed
        return result

    def stream_message(self, user_id: str, session_id: str, message: str) -> Iterator[dict]:
        self.chats.ensure_session(user_id, session_id)
        user_message_id = self.chats.save_message(session_id, "user", message)
        yield self._event("user_echo", session_id=session_id, text=message, detail={"message_id": user_message_id})
        try:
            yield self._event("status", session_id=session_id, text="正在分析问题")
            yield self._event("tool", session_id=session_id, tool="parser", text="解析用户输入")
            parsed = self.runtime.parser.parse(message)
            yield self._event("agent", session_id=session_id, agent="planner", text="planner 正在分派任务")
            plan = self.runtime.planner.run(user_id, session_id, message, parsed)
            route = plan.get("route", "planner")
            yield self._event("status", session_id=session_id, text="正在读取健康档案与会话上下文")
            yield self._event("tool", session_id=session_id, tool="memory", text="读取档案和历史上下文")
            profile = self.runtime.memory.read_profile(user_id)
            session_ctx = self.runtime.memory.read_session_context(session_id)
            yield self._event("agent", session_id=session_id, agent=route, text=self._route_message(route))
            yield self._event("tool", session_id=session_id, tool=self._tool_name(route), text=self._tool_message(route))
            result, _, _, user_message_id = self._execute_message(
                user_id,
                session_id,
                message,
                parsed=parsed,
                plan=plan,
                profile=profile,
                session_ctx=session_ctx,
                session_exists=True,
                user_message_id=user_message_id,
            )

            if plan.get("need_memory_write"):
                yield self._event("tool", session_id=session_id, tool="memory", text="已写入会话记忆")

            answer = result.get("answer", "")
            if answer:
                for chunk in self._chunk_text(answer):
                    yield self._event("assistant_delta", session_id=session_id, text=chunk, agent=result.get("current_agent"))
                yield self._event(
                    "assistant_done",
                    session_id=session_id,
                    text=answer,
                    agent=result.get("current_agent"),
                    detail={"message_id": user_message_id, "risk_level": result.get("risk_level", "low")},
                )
        except Exception as exc:
            yield self._event("error", session_id=session_id, text=f"处理失败：{exc}", detail=str(exc))
        yield self._event("done", session_id=session_id)

    def get_messages(self, user_id: str, session_id: str) -> list[dict]:
        self.chats.ensure_session(user_id, session_id)
        return self.chats.list_messages(session_id, limit=50)

    def list_sessions(self, user_id: str) -> list[dict]:
        sessions = self.chats.list_sessions(user_id)
        enriched = []
        for session in sessions:
            messages = self.chats.list_messages(session["id"], limit=8)
            title = session.get("title") or self._derive_title(messages)
            enriched.append(
                {
                    **session,
                    "display_title": title,
                    "message_count": len(messages),
                    "preview": self._preview(messages),
                    "last_activity_at": self._last_activity(session, messages),
                }
            )
        enriched.sort(key=lambda item: (item["last_activity_at"], item["id"]), reverse=True)
        return enriched

    def delete_session(self, user_id: str, session_id: str) -> dict:
        self.chats.delete_session(user_id, session_id)
        return {"deleted_session_id": session_id}

    def clear_sessions(self, user_id: str) -> dict:
        self.chats.clear_sessions(user_id)
        return {"cleared": True}

    def _derive_title(self, messages: list[dict]) -> str:
        for message in messages:
            if message.get("role") == "user" and message.get("content"):
                content = message["content"].strip().replace("\n", " ")
                return content[:16] + ("..." if len(content) > 16 else "")
        return "未命名会话"

    def _preview(self, messages: list[dict]) -> str:
        for message in reversed(messages):
            content = (message.get("content") or "").strip().replace("\n", " ")
            if content:
                return content[:28] + ("..." if len(content) > 28 else "")
        return ""

    def _last_activity(self, session: dict, messages: list[dict]) -> str:
        if messages:
            return messages[-1].get("created_at") or session.get("started_at") or ""
        return session.get("started_at") or ""

    def _execute_message(
        self,
        user_id: str,
        session_id: str,
        message: str,
        *,
        parsed: dict | None = None,
        plan: dict | None = None,
        profile: dict | None = None,
        session_ctx: list[dict] | None = None,
        session_exists: bool = False,
        user_message_id: int | None = None,
    ) -> tuple[dict, dict, dict, int]:
        if not session_exists:
            self.chats.ensure_session(user_id, session_id)
        if user_message_id is None:
            user_message_id = self.chats.save_message(session_id, "user", message)
        parsed = parsed if parsed is not None else self.runtime.parser.parse(message)
        plan = plan if plan is not None else self.runtime.planner.run(user_id, session_id, message, parsed)
        profile = profile if profile is not None else self.runtime.memory.read_profile(user_id)
        session_ctx = session_ctx if session_ctx is not None else self.runtime.memory.read_session_context(session_id)

        if plan["route"] == "symptom_agent":
            result = self.runtime.symptom_agent.run(message, parsed, profile, session_ctx, plan["risk_level"])
        elif plan["route"] == "drug_agent":
            result = self.runtime.drug_agent.run(message, parsed, profile)
        elif plan["route"] == "data_agent":
            result = self.runtime.data_agent.run(user_id, parsed)
        elif plan["route"] == "reminder_agent":
            result = self.runtime.reminder_agent.run(user_id, parsed, profile)
        else:
            result = self.runtime.planner.build_general_chat(message, parsed, profile, session_ctx)

        if plan.get("need_memory_write"):
            self.runtime.memory.maybe_persist(user_id, session_id, parsed, source_message_id=user_message_id)

        answer = result.get("answer", "")
        if answer:
            self.chats.save_message(session_id, "assistant", answer)

        return result, parsed, plan, user_message_id

    def _event(self, event_type: str, **payload) -> dict:
        return {"type": event_type, "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), **payload}

    def _chunk_text(self, text: str) -> list[str]:
        normalized = text.strip()
        if not normalized:
            return []
        chunks: list[str] = []
        current = ""
        for char in normalized:
            current += char
            if len(current) >= 24 or char in {"。", "！", "？", "\n"}:
                chunks.append(current)
                current = ""
        if current:
            chunks.append(current)
        return chunks

    def _route_message(self, route: str) -> str:
        labels = {
            "symptom_agent": "symptom_agent 正在整理症状建议",
            "drug_agent": "drug_agent 正在核对用药信息",
            "data_agent": "data_agent 正在记录健康指标",
            "reminder_agent": "reminder_agent 正在生成提醒",
            "planner": "planner 正在组织回复",
            "general_chat_agent": "general_chat_agent 正在生成回复",
        }
        return labels.get(route, f"{route} 正在处理")

    def _tool_name(self, route: str) -> str:
        mapping = {
            "symptom_agent": "rag",
            "drug_agent": "rag",
            "data_agent": "record_store",
            "reminder_agent": "scheduler",
        }
        return mapping.get(route, "copilot")

    def _tool_message(self, route: str) -> str:
        labels = {
            "symptom_agent": "检索症状相关知识",
            "drug_agent": "检索药物与禁忌信息",
            "data_agent": "写入健康记录并汇总趋势",
            "reminder_agent": "创建提醒并同步调度器",
        }
        return labels.get(route, "生成回复")
