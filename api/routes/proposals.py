"""API routes for creating Qwilr proposal pages."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from proposal_qwilr.client import QwilrClient, QwilrProposalService, QwilrAPIError
from proposal_qwilr.mapper import ProposalToQwilrMapper
from proposal_qwilr.schemas import ProposalSchema, QwilrConfig, QwilrPageResult

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_db(config: QwilrConfig):
    """Get database connection if Supabase is configured."""
    if not config.supabase_configured:
        return None
    try:
        from proposal_qwilr.database import ProposalDatabase
        return ProposalDatabase(config)
    except Exception as e:
        logger.warning("Supabase not available: %s", e)
        return None


@router.post("/create", response_model=QwilrPageResult)
async def create_proposal(
    proposal: ProposalSchema,
    publish: bool = False,
    force_new: bool = False,
):
    """Create a Qwilr page from proposal data.

    Idempotent by default: if proposal_id already has a Qwilr page,
    returns the existing page. Use force_new=true to create a new page anyway.
    """
    config = QwilrConfig()  # type: ignore[call-arg]
    db = _get_db(config)

    # Idempotency check
    if db and not force_new:
        try:
            existing = db.get_proposal(proposal.proposal_id)
            if existing and existing.get("qwilr_page_id"):
                logger.info(
                    "Proposal %s already has Qwilr page %s — returning existing",
                    proposal.proposal_id, existing["qwilr_page_id"],
                )
                return QwilrPageResult(
                    page_id=existing["qwilr_page_id"],
                    url=existing.get("qwilr_url", ""),
                    share_url=existing.get("qwilr_share_url", ""),
                    status=existing.get("qwilr_status", "published"),
                )
        except Exception as e:
            logger.warning("Idempotency check failed: %s — proceeding", e)

    mapper = ProposalToQwilrMapper()
    client = QwilrClient(config)
    service = QwilrProposalService(client, config)

    try:
        page_request = mapper.build_create_page_request(proposal, config.template_id)
        quote_sections = mapper.build_quote_sections(proposal.investment)

        result = await service.create_proposal_page(
            page_request, quote_sections, publish=publish
        )

        # Save to database
        if db:
            try:
                db.upsert_proposal(
                    proposal_id=proposal.proposal_id,
                    title=proposal.title,
                    client_company=proposal.client.company,
                    client_contact=proposal.client.contact,
                    client_email=proposal.client.email,
                    proposal_data=proposal.model_dump(),
                    valid_until=proposal.valid_until,
                )
                db.update_qwilr_info(proposal.proposal_id, result)
            except Exception as e:
                logger.warning("Failed to save to database: %s", e)

        return result

    except QwilrAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await client.close()


@router.put("/update/{proposal_id}", response_model=QwilrPageResult)
async def update_proposal(proposal_id: str, proposal: ProposalSchema):
    """Update an existing Qwilr page with new proposal data."""
    config = QwilrConfig()  # type: ignore[call-arg]
    db = _get_db(config)

    if not db:
        raise HTTPException(
            status_code=503,
            detail="Supabase required for update — cannot look up existing page",
        )

    existing = db.get_proposal(proposal_id)
    if not existing or not existing.get("qwilr_page_id"):
        raise HTTPException(
            status_code=404,
            detail=f"No existing Qwilr page found for proposal {proposal_id}",
        )

    mapper = ProposalToQwilrMapper()
    client = QwilrClient(config)

    try:
        subs = mapper.build_substitutions(proposal)
        await client.update_page(existing["qwilr_page_id"], substitutions=subs)

        # Update DB with new proposal data
        db.upsert_proposal(
            proposal_id=proposal.proposal_id,
            title=proposal.title,
            client_company=proposal.client.company,
            client_contact=proposal.client.contact,
            client_email=proposal.client.email,
            proposal_data=proposal.model_dump(),
            valid_until=proposal.valid_until,
        )

        return QwilrPageResult(
            page_id=existing["qwilr_page_id"],
            url=existing.get("qwilr_url", ""),
            share_url=existing.get("qwilr_share_url", ""),
            status=existing.get("qwilr_status", "published"),
        )

    except QwilrAPIError as e:
        raise HTTPException(status_code=e.status_code or 502, detail=str(e))
    finally:
        await client.close()
