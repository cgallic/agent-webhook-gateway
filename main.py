"""
CMO Agent System - Webhook Gateway

FastAPI application exposing Python automation scripts via HTTP endpoints.
"""

import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from gateway.config import config
from gateway.auth import verify_api_key
from gateway.jobs import job_queue
from gateway.models import WebhookResponse

# Import routers
from gateway.routers import analytics, tiktok, cold_email, tasks, clients, jobs
from gateway.routers import whatsapp, agent, creative, stripe, quality, mikai
from gateway.routers import demo


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print(f"CMO Gateway starting on {config.host}:{config.port}")
    print(f"Debug mode: {config.debug}")

    # Cleanup old jobs on startup
    job_queue.cleanup_old_jobs(days=7)

    yield

    # Shutdown
    print("CMO Gateway shutting down...")
    job_queue.shutdown()


# Create FastAPI app
app = FastAPI(
    title="CMO Agent System Gateway",
    description="Webhook gateway for marketing automation scripts",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if config.debug else None,
    redoc_url="/redoc" if config.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if config.debug else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Health Check (No Auth Required)
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint - no authentication required."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "CMO Agent System Gateway",
        "version": "1.0.0",
        "docs": "/docs" if config.debug else "Disabled in production",
        "endpoints": {
            "health": "/health",
            "analytics": "/webhooks/analytics/*",
            "tiktok": "/webhooks/tiktok/*",
            "cold_email": "/webhooks/cold-email/*",
            "whatsapp": "/webhooks/whatsapp/*",
            "creative": "/webhooks/creative/*",
            "stripe": "/stripe/*",
            "tasks": "/webhooks/tasks/*",
            "clients": "/clients",
            "jobs": "/jobs/*",
            "agent": "/agent/*",
            "quality": "/webhooks/quality/*",
            "mikai": "/api/mikai/*"
        }
    }


# ============================================================================
# Include Routers
# ============================================================================

# All webhook routes require API key
app.include_router(
    analytics.router,
    prefix="/webhooks/analytics",
    tags=["Analytics"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    tiktok.router,
    prefix="/webhooks/tiktok",
    tags=["TikTok"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    cold_email.router,
    prefix="/webhooks/cold-email",
    tags=["Cold Email"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    tasks.router,
    prefix="/webhooks/tasks",
    tags=["Tasks"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    clients.router,
    prefix="/clients",
    tags=["Clients"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    jobs.router,
    prefix="/jobs",
    tags=["Jobs"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    whatsapp.router,
    prefix="/webhooks/whatsapp",
    tags=["WhatsApp"],
    # Note: WhatsApp webhook must verify Twilio signature, not API key
)

app.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    creative.router,
    prefix="/webhooks/creative",
    tags=["Creative"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    stripe.router,
    prefix="/stripe",
    tags=["Stripe"],
    dependencies=[Depends(verify_api_key)]
)

app.include_router(
    quality.router,
    prefix="/webhooks/quality",
    tags=["Quality"],
    dependencies=[Depends(verify_api_key)]
)

# MiKai audit routes — /audit is public (no auth), /leads + /run require API key
app.include_router(
    mikai.router,
    prefix="/api/mikai",
    tags=["MiKai"],
    # Auth handled per-route inside the router (audit is public, leads/run need key)
)

# Demo routes — public, self-contained example of the async job flow.
# API-key protected like the other webhooks.
app.include_router(
    demo.router,
    prefix="/demo",
    tags=["Demo"],
    dependencies=[Depends(verify_api_key)]
)


# ============================================================================
# Static Files (optional — guarded so a missing dep/dir can't break startup)
# ============================================================================

# Serve the demo dashboard at /static/dashboard.html. Wrapped in try/except so
# the gateway still boots if StaticFiles is unavailable or the directory is
# absent in a given deployment.
try:
    from fastapi.staticfiles import StaticFiles

    _static_dir = Path(__file__).parent / "static"
    if _static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")
except Exception as _static_err:  # pragma: no cover - best-effort mount
    print(f"Static files not mounted: {_static_err}")


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    """Run the gateway server."""
    import uvicorn

    uvicorn.run(
        "gateway.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="debug" if config.debug else "info"
    )


if __name__ == "__main__":
    main()
