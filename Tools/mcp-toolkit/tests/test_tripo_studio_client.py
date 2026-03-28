"""Unit tests for Tripo Studio client pure helpers."""

from veilbreakers_mcp.shared.tripo_studio_client import TripoStudioClient


class TestTripoStudioJwtParsing:
    """Malformed JWTs should fail closed without raising."""

    def test_parse_jwt_exp_returns_zero_for_malformed_token(self):
        assert TripoStudioClient._parse_jwt_exp("not-a-jwt") == 0.0

    def test_parse_jwt_exp_returns_zero_for_invalid_payload(self):
        assert TripoStudioClient._parse_jwt_exp("a.invalid!.c") == 0.0
