"""Map proposal data to Qwilr API payloads."""
from __future__ import annotations

import html

from proposal_qwilr.html_renderer import render_list_html, render_scope_html, render_timeline_html
from proposal_qwilr.schemas import (
    Investment,
    InvestmentTier,
    ProposalSchema,
    QwilrCreatePageRequest,
    QwilrLineItem,
    QwilrQuoteSection,
    QwilrSubstitutions,
    parse_price,
)


def _esc(value: str) -> str:
    """Escape user-provided text for safe HTML embedding."""
    return html.escape(value, quote=True)


class ProposalToQwilrMapper:
    """Transforms a ProposalSchema into Qwilr API payloads."""

    def build_substitutions(self, proposal: ProposalSchema) -> dict[str, str]:
        """Build template token substitutions from proposal data."""
        subs = QwilrSubstitutions(
            title=_esc(proposal.title),
            client_company=_esc(proposal.client.company),
            executive_summary=_esc(proposal.executive_summary),
            understanding=f"<h2>Our Understanding</h2><p>{_esc(proposal.understanding)}</p>",
            approach=f"<h2>Our Approach</h2><p>{_esc(proposal.approach)}</p>",
            scope_html=render_scope_html(proposal.scope),
            timeline_html=render_timeline_html(proposal.timeline),
            why_us_html=render_list_html(proposal.why_us, title="Why Choose Us"),
            next_steps_html=render_list_html(proposal.next_steps, ordered=True, title="Next Steps"),
            valid_until=f"<p style='color:#6b7280;font-size:14px;text-align:center;'>"
                        f"This proposal is valid until {_esc(proposal.valid_until)}</p>",
        )
        return subs.model_dump()

    def build_quote_sections(self, investment: Investment) -> list[dict]:
        """Build Qwilr quote sections from investment tiers."""
        sections = []
        for tier_key in ("good", "better", "best"):
            tier: InvestmentTier = getattr(investment, tier_key)
            price = parse_price(tier.price)
            line_items = [
                QwilrLineItem(
                    description=item,
                    unitPrice=0,
                    featuresList=[],
                )
                for item in tier.includes
            ]
            section = QwilrQuoteSection(
                title=tier.name,
                description=f"{tier.name} — {tier.price}",
                lineItems=line_items,
                settings={
                    "showSubtotal": True,
                    "showUnitPrice": False,
                    "showQuantity": False,
                    "showCost": True,
                    "selected": tier_key == "better",
                },
            )
            # Set the total price on the first line item
            if line_items:
                line_items[0].unitPrice = price
            sections.append(section.model_dump())
        return sections

    def build_create_page_request(
        self, proposal: ProposalSchema, template_id: str
    ) -> QwilrCreatePageRequest:
        """Build the full Qwilr create page request."""
        return QwilrCreatePageRequest(
            templateId=template_id,
            name=f"Proposal: {proposal.title} — {proposal.client.company}",
            published=False,
            substitutions=self.build_substitutions(proposal),
            metadata={
                "proposal_id": proposal.proposal_id,
                "client_company": proposal.client.company,
                "client_email": proposal.client.email,
            },
            tags=["proposal", "auto-generated"],
        )
