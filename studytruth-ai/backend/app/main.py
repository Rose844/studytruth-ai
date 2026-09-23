from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.core.vector_store import rebuild_vector_store
from app.utils.logger import get_logger
from app.routers import documents, ask, conflicts, exam, quiz, analytics

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info(f"Starting StudyTruth AI backend (env={settings.APP_ENV})")
    log.info(f"Foundry LLM mode: {'FOUNDRY (cloud)' if settings.HAS_FOUNDRY_LLM else 'LOCAL MOCK (offline)'}")
    log.info(f"Azure AI Search mode: {'AZURE SEARCH (cloud)' if settings.HAS_AZURE_SEARCH else 'LOCAL VECTOR STORE (offline)'}")
    init_db()
    rebuild_vector_store()
    yield


app = FastAPI(
    title="StudyTruth AI API",
    description="Intelligent study assistant with Knowledge Conflict Detection, "
                 "grounded RAG retrieval, and an agentic Study Assistant.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.FRONTEND_ORIGIN == "*" else [settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router)
app.include_router(ask.router)
app.include_router(conflicts.router)
app.include_router(exam.router)
app.include_router(quiz.router)
app.include_router(analytics.router)


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": {
            "llm": "foundry" if settings.HAS_FOUNDRY_LLM else "local_mock",
            "search": "azure_ai_search" if settings.HAS_AZURE_SEARCH else "local_vector_store",
            "foundry_iq_enabled": settings.FOUNDRY_IQ_ENABLED,
        },
    }
