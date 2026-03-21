"""FastAPI application for Proposal-to-Qwilr service."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.proposals import router as proposals_router
from api.routes.webhooks import router as webhooks_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration and connectivity on startup."""
    from proposal_qwilr.schemas import QwilrConfig
    from proposal_qwilr.client import QwilrClient

    # Validate all required env vars are present
    try:
        config = QwilrConfig()  # type: ignore[call-arg]
    except Exception as e:
        logger.critical("Missing required environment variables: %s", e)
        raise RuntimeError(f"Configuration error: {e}") from e

    # Verify Qwilr API connectivity
    client = QwilrClient(config)
    try:
        healthy = await client.health_check()
        if healthy:
            logger.info("Qwilr API connection verified")
        else:
            logger.warning("Qwilr API unreachable — service starting anyway, but API calls will fail")
    except Exception as e:
        logger.warning("Qwilr health check error: %s — starting anyway", e)
    finally:
        await client.close()

    # Log configuration summary
    logger.info(
        "Proposal-to-Qwilr starting: template=%s, quote_block=%s, env=%s",
        config.template_id,
        config.quote_block_id or "(none)",
        config.app_env,
    )

    yield

    logger.info("Proposal-to-Qwilr shutting down")


app = FastAPI(
    title="Proposal-to-Qwilr",
    description="Convert structured proposals into interactive Qwilr pages",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(proposals_router, prefix="/api/proposals", tags=["proposals"])
app.include_router(webhooks_router, prefix="/webhooks", tags=["webhooks"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "proposal-to-qwilr"}
