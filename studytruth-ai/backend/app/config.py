"""
Central configuration for StudyTruth AI backend.

All secrets are read from environment variables (via .env in local dev).
Nothing here is hardcoded. If Foundry / Azure AI Search credentials are not
supplied, the app transparently falls back to local, offline implementations
so the product remains fully demoable without any cloud dependency.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
PROJECT_ROOT = BASE_DIR.parent                              # studytruth-ai/
load_dotenv(PROJECT_ROOT / ".env")


def _bool(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    # Foundry (LLM)
    FOUNDRY_ENDPOINT: str = os.getenv("FOUNDRY_ENDPOINT", "").strip()
    FOUNDRY_API_KEY: str = os.getenv("FOUNDRY_API_KEY", "").strip()
    FOUNDRY_MODEL: str = os.getenv("FOUNDRY_MODEL", "gpt-4o-mini").strip()
    FOUNDRY_API_VERSION: str = os.getenv("FOUNDRY_API_VERSION", "2024-05-01-preview").strip()

    # Foundry IQ
    FOUNDRY_IQ_KNOWLEDGE_SOURCE: str = os.getenv("FOUNDRY_IQ_KNOWLEDGE_SOURCE", "").strip()
    FOUNDRY_IQ_ENABLED: bool = _bool("FOUNDRY_IQ_ENABLED")

    # Azure AI Search
    AZURE_SEARCH_ENDPOINT: str = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
    AZURE_SEARCH_API_KEY: str = os.getenv("AZURE_SEARCH_API_KEY", "").strip()
    AZURE_SEARCH_INDEX: str = os.getenv("AZURE_SEARCH_INDEX", "studytruth-documents").strip()

    # Behaviour
    FORCE_LOCAL_MODE: bool = _bool("FORCE_LOCAL_MODE", "true")
    APP_ENV: str = os.getenv("APP_ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "*")

    # Derived flags: do we actually have usable cloud credentials?
    @property
    def HAS_FOUNDRY_LLM(self) -> bool:
        return bool(self.FOUNDRY_ENDPOINT and self.FOUNDRY_API_KEY) and not self.FORCE_LOCAL_MODE

    @property
    def HAS_AZURE_SEARCH(self) -> bool:
        return bool(self.AZURE_SEARCH_ENDPOINT and self.AZURE_SEARCH_API_KEY) and not self.FORCE_LOCAL_MODE

    # Paths
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = DATA_DIR / "uploads"
    STORAGE_DIR: Path = DATA_DIR / "storage"
    DB_PATH: Path = STORAGE_DIR / "studytruth.db"
    VECTOR_INDEX_PATH: Path = STORAGE_DIR / "vector_index.pkl"

    # Retrieval
    CHUNK_SIZE: int = 900          # characters per chunk
    CHUNK_OVERLAP: int = 150
    TOP_K: int = 6


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
