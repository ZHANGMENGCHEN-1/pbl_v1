from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .shared import store
from .projects.astronomy.routes import router as astronomy_router
from .projects.library.routes import router as library_router
from .projects.library import state as library_state
from .projects.registry import router as projects_router


@asynccontextmanager
async def lifespan(app):
    store.init()
    library_state.init()
    yield


app = FastAPI(title="PBL Agent Workspace", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["GET", "PUT", "POST"], allow_headers=["Content-Type", "X-Session-ID"])
app.include_router(projects_router)
app.include_router(library_router)
app.include_router(astronomy_router)


@app.get("/api/health")
def health():
    import os
    return {"status": "ok", "llm_configured": bool(os.getenv("LLM_API_KEY"))}
