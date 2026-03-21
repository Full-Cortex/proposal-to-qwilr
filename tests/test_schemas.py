"""Tests for Pydantic schemas and validation."""
import pytest
from pydantic import ValidationError

from proposal_qwilr.schemas import (
    ProposalSchema,
    ScopeItem,
    TimelinePhase,
    InvestmentTier,
    Investment,
    ClientInfo,
    QwilrSubstitutions,
    QwilrCreatePageRequest,
    parse_price,
)


class TestParsePrice:
    def test_simple_dollar(self):
        assert parse_price("$15,000") == 15000.0

    def test_no_currency_symbol(self):
        assert parse_price("30000") == 30000.0

    def test_with_k_suffix(self):
        assert parse_price("$15k") == 15000.0

    def test_with_K_suffix(self):
        assert parse_price("$50K") == 50000.0

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="no numeric value"):
            parse_price("")

    def test_tbd_raises(self):
        with pytest.raises(ValueError, match="no numeric value"):
            parse_price("TBD")

    def test_contact_us_raises(self):
        with pytest.raises(ValueError, match="no numeric value"):
            parse_price("Contact us")

    def test_with_spaces(self):
        assert parse_price("$ 25,000") == 25000.0

    def test_decimals(self):
        assert parse_price("$1,500.50") == 1500.50


class TestInvestmentTierValidation:
    def test_valid_price(self):
        tier = InvestmentTier(name="Starter", price="$15,000", includes=["Item 1"])
        assert tier.price == "$15,000"

    def test_rejects_tbd_price(self):
        with pytest.raises(ValidationError, match="numeric value"):
            InvestmentTier(name="Starter", price="TBD", includes=["Item 1"])

    def test_rejects_contact_us_price(self):
        with pytest.raises(ValidationError, match="numeric value"):
            InvestmentTier(name="Starter", price="Contact us", includes=["Item 1"])

    def test_allows_price_with_range(self):
        tier = InvestmentTier(name="Starter", price="$10,000-15,000", includes=["Item 1"])
        assert tier.price == "$10,000-15,000"


class TestProposalSchema:
    def test_valid_proposal(self, sample_proposal_data):
        proposal = ProposalSchema(**sample_proposal_data)
        assert proposal.proposal_id == "PROP-1710700000"
        assert proposal.title == "Website Redesign & Digital Transformation"
        assert proposal.client.company == "Acme Corp"
        assert len(proposal.scope) == 5
        assert len(proposal.timeline) == 4
        assert proposal.investment.good.name == "Starter"
        assert proposal.investment.better.name == "Professional"
        assert proposal.investment.best.name == "Enterprise"

    def test_invalid_proposal_id(self, sample_proposal_data):
        sample_proposal_data["proposal_id"] = "INVALID-123"
        with pytest.raises(ValidationError):
            ProposalSchema(**sample_proposal_data)

    def test_missing_required_field(self, sample_proposal_data):
        del sample_proposal_data["title"]
        with pytest.raises(ValidationError):
            ProposalSchema(**sample_proposal_data)

    def test_empty_scope(self, sample_proposal_data):
        sample_proposal_data["scope"] = []
        proposal = ProposalSchema(**sample_proposal_data)
        assert proposal.scope == []

    def test_internal_notes_optional(self, sample_proposal_data):
        del sample_proposal_data["internal_notes"]
        proposal = ProposalSchema(**sample_proposal_data)
        assert proposal.internal_notes == ""

    def test_title_max_length(self, sample_proposal_data):
        sample_proposal_data["title"] = "x" * 501
        with pytest.raises(ValidationError):
            ProposalSchema(**sample_proposal_data)


class TestQwilrModels:
    def test_substitutions_defaults(self):
        subs = QwilrSubstitutions()
        assert subs.title == ""
        assert subs.client_company == ""

    def test_create_page_request(self):
        req = QwilrCreatePageRequest(
            templateId="tmpl-123",
            name="Test Proposal",
        )
        assert req.templateId == "tmpl-123"
        assert req.published is False
        assert req.tags == []
