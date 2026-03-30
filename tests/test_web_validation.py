"""Tests for WebSocket input validation."""

from aidm.web import _validate_ws_field


class TestValidateWsField:
    """_validate_ws_field should truncate oversized strings."""

    def test_normal_input_unchanged(self):
        assert _validate_ws_field("hello", 50) == "hello"

    def test_empty_returns_default(self):
        assert _validate_ws_field("", 50, "fallback") == "fallback"

    def test_none_returns_default(self):
        assert _validate_ws_field(None, 50, "fallback") == "fallback"

    def test_oversized_truncated(self):
        long = "a" * 100
        result = _validate_ws_field(long, 50)
        assert len(result) == 50

    def test_strips_whitespace(self):
        assert _validate_ws_field("  hello  ", 50) == "hello"
