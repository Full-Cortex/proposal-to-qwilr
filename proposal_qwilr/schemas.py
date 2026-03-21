"""Pydantic schemas for proposal data and Qwilr API payloads."""
from __future__ import annotations

import logging
import re
from datetime import datetime, date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)

# --- Config ---


class QwilrConfig(BaseSettings):
    """Configuration loaded from environment variables."""
    api_key: str = Field(alias="QWILR_API_KEY")
    base_url: str = Field(default="https://api.qwilr.com/v1", alias="QWILR_BASE_URL")
    template_id: str = Field(alias="QWILR_TEMPLATE_ID")
    quote_block_id: str = Field(default="", alias="QWILR_QUOTE_BLOCK_ID")
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")
    webhook_base_url: str = Field(default="", alias="WEBHOOK_BASE_URL")
    slack_webhook_url: str = Field(default="", alias="SLACK_WEBHOOK_URL")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_port: int = Field(default=8000, alias="APP_PORT")

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def supabase_configured(self) -> bool:
        """Check if Supabase credentials are provided."""
        return bool(self.supabase_url and self.supabase_key)


# --- Proposal Input Models (matches n8n generator output) ---


class ScopeItem(BaseModel):
    """A single scope/deliverable item."""
    deliverable: str = Field(max_length=500)
    description: str = Field(max_length=2000)


class TimelinePhase(BaseModel):
    """A single phase in the project timeline."""
    phase: str = Field(max_length=200)
    duration: str = Field(max_length=100)
    deliverables: list[str] = Field(max_length=50)


class InvestmentTier(BaseModel):
    """A pricing tier (good/better/best)."""
    name: str = Field(max_length=100)
    price: str = Field(max_length=50)
    includes: list[str] = Field(max_length=30)

    @field_validator("price")
    @classmethod
    def validate_price(cls, v: str) -> str:
        """Ensure price contains at least one digit (reject TBD, Contact us, etc.)."""
        if not re.search(r"\d", v):
            raise ValueError(
                f"Price must contain a numeric value, got '{v}'. "
                "Use a dollar amount like '$15,000' or '$15k'."
            )
        return v


class Investment(BaseModel):
    """Three-tier investment options."""
    good: InvestmentTier
    better: InvestmentTier
    best: InvestmentTier


class ClientInfo(BaseModel):
    """Client contact information."""
    company: str = Field(max_length=255)
    contact: str = Field(max_length=255)
    email: str = Field(max_length=255)


class ProposalSchema(BaseModel):
    """Full proposal as output by the n8n proposal generator."""
    proposal_id: str = Field(pattern=r"^PROP-\d+$")
    title: str = Field(max_length=500)
    executive_summary: str = Field(max_length=10000)
    understanding: str = Field(max_length=10000)
    approach: str = Field(max_length=10000)
    scope: list[ScopeItem] = Field(max_length=50)
    timeline: list[TimelinePhase] = Field(max_length=20)
    investment: Investment
    why_us: list[str] = Field(max_length=20)
    next_steps: list[str] = Field(max_length=20)
    valid_until: str
    internal_notes: str = ""
    client: ClientInfo
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    @field_validator("valid_until")
    @classmethod
    def validate_valid_until(cls, v: str) -> str:
        """Warn if proposal is already expired (but don't reject — might be intentional)."""
        try:
            parsed = date.fromisoformat(v)
            if parsed < date.today():
                logger.warning("Proposal valid_until date %s is in the past", v)
        except ValueError:
            pass  # Non-date strings are allowed (e.g., "30 days from signing")
        return v


# --- Qwilr API Models ---


class QwilrSubstitutions(BaseModel):
    """Token substitutions for Qwilr template."""
    title: str = ""
    client_company: str = ""
    executive_summary: str = ""
    understanding: str = ""
    approach: str = ""
    scope_html: str = ""
    timeline_html: str = ""
    why_us_html: str = ""
    next_steps_html: str = ""
    valid_until: str = ""


class QwilrLineItem(BaseModel):
    """A line item in a Qwilr quote section."""
    type: str = "fixedCost"
    description: str
    unitPrice: float = 0
    quantity: int = 1
    optional: bool = False
    selected: bool = True
    featuresList: list[str] = Field(default_factory=list)


class QwilrQuoteSection(BaseModel):
    """A section in the Qwilr quote block (one per pricing tier)."""
    title: str = ""
    description: str = ""
    displayMode: str = "standard"
    lineItems: list[QwilrLineItem] = Field(default_factory=list)
    settings: dict[str, Any] = Field(default_factory=lambda: {
        "showSubtotal": True,
        "showUnitPrice": True,
        "showQuantity": False,
        "showCost": True,
        "selected": True,
    })


class QwilrCreatePageRequest(BaseModel):
    """Request body for POST /pages."""
    templateId: str
    name: str
    published: bool = False
    substitutions: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class QwilrPageResult(BaseModel):
    """Result from creating a Qwilr page."""
    page_id: str
    url: str = ""
    share_url: str = ""
    status: str = "draft"


# --- Utility ---


def parse_price(price_str: str) -> float:
    """Parse a price string like '$15,000' or '$15k' into a float.

    Raises ValueError if no numeric value can be extracted.
    """
    cleaned = re.sub(r"[^\d.,kK]", "", price_str)
    if not cleaned:
        raise ValueError(f"Cannot parse price from '{price_str}' — no numeric value found")
    if cleaned.lower().endswith("k"):
        return float(cleaned[:-1].replace(",", "")) * 1000
    return float(cleaned.replace(",", ""))
