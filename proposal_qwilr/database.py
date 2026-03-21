"""Supabase database operations for proposals and events."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from proposal_qwilr.schemas import QwilrConfig, QwilrPageResult

logger = logging.getLogger(__name__)


class ProposalDatabase:
    """Handles all Supabase operations for proposal tracking.

    Uses the existing `agency_proposals` table from the n8n proposal generator
    with added Qwilr columns (added via migration).
    """

    def __init__(self, config: QwilrConfig):
        if not config.supabase_configured:
            raise RuntimeError(
                "Supabase not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"
            )
        from supabase import create_client
        self.client = create_client(config.supabase_url, config.supabase_key)

    def upsert_proposal(
        self,
        proposal_id: str,
        title: str,
        client_company: str,
        client_contact: str,
        client_email: str,
        proposal_data: dict,
        valid_until: str | None = None,
    ) -> dict:
        """Insert or update a proposal record in agency_proposals."""
        record = {
            "proposal_id": proposal_id,
            "title": title,
            "client_company": client_company,
            "client_contact": client_contact,
            "client_email": client_email,
            "proposal_data": proposal_data,
            "valid_until": valid_until,
            "status": "active",
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        result = (
            self.client.table("agency_proposals")
            .upsert(record, on_conflict="proposal_id")
            .execute()
        )
        return result.data[0] if result.data else record

    def update_qwilr_info(
        self,
        proposal_id: str,
        qwilr_result: QwilrPageResult,
    ) -> dict:
        """Store Qwilr page info on the proposal record."""
        result = (
            self.client.table("agency_proposals")
            .update({
                "qwilr_page_id": qwilr_result.page_id,
                "qwilr_url": qwilr_result.url,
                "qwilr_share_url": qwilr_result.share_url,
                "qwilr_status": qwilr_result.status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("proposal_id", proposal_id)
            .execute()
        )
        return result.data[0] if result.data else {}

    def update_qwilr_status(self, proposal_id: str, status: str, **extra) -> dict:
        """Update the Qwilr status and any additional fields."""
        update = {
            "qwilr_status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        result = (
            self.client.table("agency_proposals")
            .update(update)
            .eq("proposal_id", proposal_id)
            .execute()
        )
        return result.data[0] if result.data else {}

    def get_proposal(self, proposal_id: str) -> dict | None:
        """Fetch a proposal by proposal_id."""
        result = (
            self.client.table("agency_proposals")
            .select("*")
            .eq("proposal_id", proposal_id)
            .single()
            .execute()
        )
        return result.data

    def get_proposal_by_qwilr_page(self, qwilr_page_id: str) -> dict | None:
        """Fetch a proposal by its Qwilr page ID (for webhook lookups)."""
        result = (
            self.client.table("agency_proposals")
            .select("*")
            .eq("qwilr_page_id", qwilr_page_id)
            .single()
            .execute()
        )
        return result.data

    def list_proposals(self, limit: int = 20, status: str | None = None) -> list[dict]:
        """List proposals, optionally filtered by status."""
        query = (
            self.client.table("agency_proposals")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            query = query.eq("status", status)
        result = query.execute()
        return result.data or []

    def log_event(
        self,
        proposal_id: str,
        event_type: str,
        event_data: dict | None = None,
        source: str = "qwilr",
    ) -> dict:
        """Log a proposal event (viewed, accepted, etc.)."""
        record = {
            "proposal_id": proposal_id,
            "event_type": event_type,
            "event_data": event_data or {},
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        result = self.client.table("proposal_events").insert(record).execute()
        return result.data[0] if result.data else record
