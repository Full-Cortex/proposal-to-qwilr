"""Tests for ProposalToQwilrMapper."""
from proposal_qwilr.mapper import ProposalToQwilrMapper
from proposal_qwilr.schemas import ProposalSchema


class TestBuildSubstitutions:
    def test_maps_all_fields(self, sample_proposal):
        mapper = ProposalToQwilrMapper()
        subs = mapper.build_substitutions(sample_proposal)

        # Title has & escaped to &amp;
        assert "Website Redesign" in subs["title"]
        assert subs["client_company"] == "Acme Corp"
        assert "excited to present" in subs["executive_summary"]
        assert "Our Understanding" in subs["understanding"]
        assert "Our Approach" in subs["approach"]
        assert "<table" in subs["scope_html"]
        assert "Phase 1" in subs["timeline_html"]
        assert "Why Choose Us" in subs["why_us_html"]
        assert "Next Steps" in subs["next_steps_html"]
        assert "2026-04-17" in subs["valid_until"]

    def test_escapes_html_in_text_fields(self):
        from proposal_qwilr.schemas import ProposalSchema
        import json
        from pathlib import Path

        data = json.loads(
            (Path(__file__).parent / "fixtures" / "sample_proposal.json").read_text()
        )
        data["title"] = '<script>alert("xss")</script>'
        data["understanding"] = '<img src=x onerror="steal()">'
        proposal = ProposalSchema(**data)
        mapper = ProposalToQwilrMapper()
        subs = mapper.build_substitutions(proposal)

        # Raw tags must be escaped — no executable HTML
        assert "<script>" not in subs["title"]
        assert "<img src=x" not in subs["understanding"]
        assert "&lt;script&gt;" in subs["title"]
        assert "&lt;img" in subs["understanding"]


class TestBuildQuoteSections:
    def test_creates_three_tiers(self, sample_proposal):
        mapper = ProposalToQwilrMapper()
        sections = mapper.build_quote_sections(sample_proposal.investment)

        assert len(sections) == 3
        assert sections[0]["title"] == "Starter"
        assert sections[1]["title"] == "Professional"
        assert sections[2]["title"] == "Enterprise"

    def test_parses_prices(self, sample_proposal):
        mapper = ProposalToQwilrMapper()
        sections = mapper.build_quote_sections(sample_proposal.investment)

        # First line item of each tier should have the parsed price
        assert sections[0]["lineItems"][0]["unitPrice"] == 15000.0
        assert sections[1]["lineItems"][0]["unitPrice"] == 30000.0
        assert sections[2]["lineItems"][0]["unitPrice"] == 50000.0

    def test_includes_as_line_items(self, sample_proposal):
        mapper = ProposalToQwilrMapper()
        sections = mapper.build_quote_sections(sample_proposal.investment)

        good_items = sections[0]["lineItems"]
        assert len(good_items) == 4  # Starter has 4 includes
        assert good_items[0]["description"] == "UX Audit & Research"

    def test_better_tier_selected_by_default(self, sample_proposal):
        mapper = ProposalToQwilrMapper()
        sections = mapper.build_quote_sections(sample_proposal.investment)

        assert sections[0]["settings"]["selected"] is False  # good
        assert sections[1]["settings"]["selected"] is True   # better
        assert sections[2]["settings"]["selected"] is False  # best


class TestBuildCreatePageRequest:
    def test_builds_request(self, sample_proposal):
        mapper = ProposalToQwilrMapper()
        req = mapper.build_create_page_request(sample_proposal, "tmpl-abc")

        assert req.templateId == "tmpl-abc"
        assert "Acme Corp" in req.name
        assert req.published is False
        assert req.metadata["proposal_id"] == "PROP-1710700000"
        assert req.metadata["client_email"] == "jane@acme.com"
        assert "proposal" in req.tags
