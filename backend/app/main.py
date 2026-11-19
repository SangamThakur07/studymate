import threading
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.config import settings
from app.routers import students, agent, materials, auth

Base.metadata.create_all(bind=engine)

def _warm_models():
    """Load the embedding model once, in the background, right after the server starts."""
    try:
        from app.tools.evaluation_tools import _get_embedding_model
        _get_embedding_model().encode(["warm up"], show_progress_bar=False)
        print("[startup] embedding model ready")
    except Exception as exc:
        print(f"[startup] embedding model not available ({type(exc).__name__}); fallbacks will be used")


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_warm_models, daemon=True).start()
    yield


app = FastAPI(title="AI Study Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(students.router)
app.include_router(agent.router)
app.include_router(materials.router)


@app.get("/health")
def health():
    return {"status": "ok", "llm_provider": settings.LLM_PROVIDER, "retrieval": settings.RETRIEVAL_METHOD}


# Single-server mode: if the frontend has been built (npm run build), serve it from here too, so
# the whole app lives at ONE address. That is what makes a shareable link possible.
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
API_PREFIXES = {"auth", "students", "agent", "health", "docs", "redoc", "openapi.json"}

if (DIST / "index.html").exists():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        if full_path.split("/")[0] in API_PREFIXES:
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (DIST / full_path).resolve()
        if full_path and candidate.is_file() and DIST.resolve() in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(DIST / "index.html")   # any page route: let the React app handle it
else:
    @app.get("/")
    def root():
        return {"status": "ok", "message": "Backend running. Build the frontend (npm run build) to serve the app here."}
