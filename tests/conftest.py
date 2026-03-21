"""Shared test fixtures."""
import json
from pathlib import Path

import pytest

from proposal_qwilr.schemas import ProposalSchema


@pytest.fixture
def sample_proposal_data() -> dict:
    """Load the sample proposal JSON fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "sample_proposal.json"
    return json.loads(fixture_path.read_text())


@pytest.fixture
def sample_proposal(sample_proposal_data) -> ProposalSchema:
    """Parse the sample proposal into a validated schema."""
    return ProposalSchema(**sample_proposal_data)
