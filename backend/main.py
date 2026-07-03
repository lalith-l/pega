"""
Main FastAPI application — MORPHEUS backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from db import init_db, close_neo4j
from firewall.schema_registry import load_registry
from sla_monitor import sla_monitor_loop
import asyncio
from mock_servers import router as mock_router
from routers import court, cases
from config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Initializing MORPHEUS Backend...")
    await init_db()
    # Load schema versions into Neo4j
    try:
        await asyncio.wait_for(load_registry(), timeout=10.0)
    except asyncio.TimeoutError:
        print("⚠️  Schema registry load timed out — Neo4j may be unavailable. Continuing with empty registry.")
    except Exception as e:
        print(f"⚠️  Schema registry load failed: {e}. Continuing with empty registry.")
        
    # Start SLA Monitor
    asyncio.create_task(sla_monitor_loop())
    yield
    # Shutdown
    await close_neo4j()
    print("🛑 Shutting down.")


app = FastAPI(
    title="MORPHEUS API",
    description="Multi-agent Orchestration & Reasoning Platform for Human-Enterprise Unified Systems",
    version="1.0.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*|http://localhost:.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(court.router)
app.include_router(cases.router)
app.include_router(mock_router)


@app.get("/")
async def root():
    return {
        "system": "MORPHEUS",
        "version": "1.0.0",
        "status": "operational",
        "pillars": [
            "Architecture Court",
            "Living Case Object",
            "Hallucination Firewall",
            "Adaptive Decisioning Gate",
            "Temporal Reasoning Cortex",
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ── Init __init__ files ───────────────────────────────────────────────────────
