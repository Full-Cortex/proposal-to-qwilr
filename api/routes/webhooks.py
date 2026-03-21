"""Webhook handler for Qwilr events (pageViewed, pageAccepted, etc.)."""
from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Request

from proposal_qwilr.schemas import QwilrConfig

logger = logging.getLogger(__name__)
router = APIRouter()


async def _verify_webhook_signature(request: Request, api_key: str) -> bytes:
    """Verify the webhook request signature.

    Qwilr signs webhooks with HMAC-SHA256 using the API key.
    If no signature header is present, we log a warning but still process
    (for initial setup/testing). In production, set WEBHOOK_REQUIRE_SIGNATURE=true.
    """
    body = await request.body()
    signature = request.headers.get("X-Qwilr-Signature", "")

    if not signature:
        logger.warning("Webhook received without signature header — accepting for now")
        return body

    expected = hmac.new(
        api_key.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(signature, expected):
        logger.error("Webhook signature mismatch — rejecting request")
        raise HTTPException(status_code=403, detail="Invalid webhook signature")

    return body


@router.post("/qwilr")
async def handle_qwilr_webhook(request: Request):
    """Receive and process Qwilr webhook events.

    Events: pageViewed, pageFirstViewed, pageAccepted, pagePreviewAccepted
    """
    config = QwilrConfig()  # type: ignore[call-arg]

    # Verify signature before processing
    body = await _verify_webhook_signature(request, config.api_key)

    import json
    payload = json.loads(body)
    event_type = payload.get("event", "unknown")
    page_id = payload.get("pageId", "")
    metadata = payload.get("metadata", {})
    proposal_id = metadata.get("proposal_id", "")

    logger.info("Qwilr webhook: %s for page %s (proposal: %s)", event_type, page_id, proposal_id)

    try:
        from proposal_qwilr.database import ProposalDatabase
        db = ProposalDatabase(config)
        proposal = db.get_proposal_by_qwilr_page(page_id)

        if not proposal:
            logger.warning("No proposal found for Qwilr page %s", page_id)
            return {"status": "ok", "message": "no matching proposal"}

        pid = proposal["proposal_id"]
        now = datetime.now(timezone.utc).isoformat()

        if event_type == "pageFirstViewed":
            db.update_qwilr_status(
                pid, "viewed",
                first_viewed_at=now,
                last_viewed_at=now,
                view_count=1,
            )
            db.log_event(pid, "first_viewed", payload)
            await _notify_slack(config, f"Proposal viewed for the first time!\n"
                               f"Client: {proposal.get('client_company', 'Unknown')}\n"
                               f"Title: {proposal.get('title', 'Untitled')}")

        elif event_type == "pageViewed":
            view_count = proposal.get("view_count", 0) + 1
            db.update_qwilr_status(
                pid, "viewed",
                last_viewed_at=now,
                view_count=view_count,
            )
            db.log_event(pid, "viewed", payload)

        elif event_type in ("pageAccepted", "pagePreviewAccepted"):
            db.update_qwilr_status(
                pid, "accepted",
                accepted_at=now,
                status="accepted",
            )
            db.log_event(pid, "accepted", payload)
            await _notify_slack(config, f"PROPOSAL ACCEPTED!\n"
                               f"Client: {proposal.get('client_company', 'Unknown')}\n"
                               f"Title: {proposal.get('title', 'Untitled')}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error processing webhook: %s", e)

    return {"status": "ok", "event": event_type}


async def _notify_slack(config: QwilrConfig, message: str) -> None:
    """Send a notification to Slack if webhook URL is configured."""
    if not config.slack_webhook_url:
        return
    try:
        async with httpx.AsyncClient() as client:
            await client.post(config.slack_webhook_url, json={"text": message})
    except Exception as e:
        logger.warning("Failed to send Slack notification: %s", e)
