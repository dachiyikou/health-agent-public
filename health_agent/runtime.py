from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from uuid import uuid4

from agents.data_agent import DataAgent
from agents.drug_agent import DrugAgent
from agents.planner import PlannerAgent
from agents.reminder_agent import ReminderAgent
from agents.symptom_agent import SymptomAgent
from config import ensure_runtime_dirs, validate_required_config
from jobs.scheduler import ReminderScheduler
from memory.memory import MemoryManager
from tools.db import DBClient
from tools.logger import TraceLogger, build_logger
from tools.parser import InputParser
from tools.rag import RAGService
from tools.vector_store import VectorStoreClient


@dataclass
class Runtime:
    db: DBClient
    parser: InputParser
    vector_store: VectorStoreClient
    rag: RAGService
    memory: MemoryManager
    scheduler: ReminderScheduler
    planner: PlannerAgent
    symptom_agent: SymptomAgent
    drug_agent: DrugAgent
    data_agent: DataAgent
    reminder_agent: ReminderAgent
    logger: any
    tracer: TraceLogger


@lru_cache(maxsize=1)
def get_runtime() -> Runtime:
    ensure_runtime_dirs()
    validate_required_config()
    logger = build_logger("health_agent")
    tracer = TraceLogger(logger)

    db = DBClient()
    db.init_tables()

    vector_store = VectorStoreClient()
    vector_store.healthcheck()
    vector_store.ensure_collections()

    rag = RAGService(vector_store)
    memory = MemoryManager(db, vector_store)
    scheduler = ReminderScheduler(db)
    scheduler.start()

    planner = PlannerAgent()
    symptom_agent = SymptomAgent(rag)
    drug_agent = DrugAgent(rag, db)
    data_agent = DataAgent(db)
    reminder_agent = ReminderAgent(db, scheduler)

    tracer.ping_langfuse()

    return Runtime(
        db=db,
        parser=InputParser(),
        vector_store=vector_store,
        rag=rag,
        memory=memory,
        scheduler=scheduler,
        planner=planner,
        symptom_agent=symptom_agent,
        drug_agent=drug_agent,
        data_agent=data_agent,
        reminder_agent=reminder_agent,
        logger=logger,
        tracer=tracer,
    )


def create_session_id() -> str:
    return uuid4().hex
