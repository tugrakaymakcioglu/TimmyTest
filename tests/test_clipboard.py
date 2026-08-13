"""Tests for clipboard utilities."""

from timmytest.prompt.clipboard import copy_to_clipboard


def test_copy_to_clipboard():
    # Verify copy_to_clipboard does not crash and returns a boolean
    result = copy_to_clipboard("Test prompt content")
    assert isinstance(result, bool)
