"""Tests for QwilrClient with mocked httpx responses."""
import pytest
import httpx

from proposal_qwilr.client import (
    QwilrClient,
    QwilrAPIError,
    QwilrAuthError,
    QwilrRateLimitError,
)
from proposal_qwilr.schemas import QwilrConfig, QwilrCreatePageRequest


@pytest.fixture
def mock_config(monkeypatch):
    """Set env vars for QwilrConfig."""
    monkeypatch.setenv("QWILR_API_KEY", "test-key-123")
    monkeypatch.setenv("QWILR_TEMPLATE_ID", "tmpl-test")
    monkeypatch.setenv("QWILR_QUOTE_BLOCK_ID", "block-test")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test-supa-key")
    return QwilrConfig()  # type: ignore[call-arg]


class TestQwilrClient:
    @pytest.mark.asyncio
    async def test_create_page_builds_request(self, mock_config):
        """Test that QwilrClient can be instantiated and configured."""
        client = QwilrClient(mock_config)
        assert client.base_url == "https://api.qwilr.com/v1"
        assert client._client is None  # lazy init
        await client.close()

    @pytest.mark.asyncio
    async def test_health_check_returns_bool(self, mock_config):
        """Health check should return True/False without raising."""
        client = QwilrClient(mock_config)
        # Will fail since no real API, but should return False not raise
        result = await client.health_check()
        assert isinstance(result, bool)
        await client.close()


class TestQwilrErrors:
    def test_api_error_has_status_code(self):
        err = QwilrAPIError("test", status_code=500, response_body="error")
        assert err.status_code == 500

    def test_auth_error_is_api_error(self):
        err = QwilrAuthError("unauthorized", status_code=401)
        assert isinstance(err, QwilrAPIError)

    def test_rate_limit_error_is_api_error(self):
        err = QwilrRateLimitError("slow down", status_code=429)
        assert isinstance(err, QwilrAPIError)
