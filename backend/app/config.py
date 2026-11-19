import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _secret_key() -> str:
    """Key that signs login tokens. Use SECRET_KEY from .env if set; otherwise create a random
    one ONCE and keep it in backend/.secret_key, so there is never a guessable default key and
    logins survive a server restart."""
    env = os.getenv("SECRET_KEY")
    if env:
        return env
    path = Path(__file__).resolve().parents[1] / ".secret_key"
    try:
        if path.exists():
            return path.read_text().strip()
        key = secrets.token_hex(32)
        path.write_text(key)
        return key
    except OSError:
        return secrets.token_hex(32)   # read-only disk: random per run (logins reset on restart)


class Settings:
    # Toggle this once you have a real API key. Everything else in the
    # codebase reads from LLM_PROVIDER, never hardcodes "mock" or "real".
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "mock")  # "mock" | "gemini" | "groq" | "anthropic" | "openai"

    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # How passages are ranked: "auto" (embeddings, else tf-idf), "embeddings", "tfidf" or "hybrid".
    # Choose using the numbers from eval/run_eval.py on your own notes.
    RETRIEVAL_METHOD: str = os.getenv("RETRIEVAL_METHOD", "auto")

    SECRET_KEY: str = _secret_key()

    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "15"))

    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./studymate.db")

    CORS_ORIGINS: list = ["http://localhost:5173", "http://127.0.0.1:5173"]


settings = Settings()
