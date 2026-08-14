"""Tests for banner and styling utilities."""

from timmytest.banner import (
    make_header_panel,
    print_banner,
    show_fullscreen_splash,
)


def test_banner_functions():
    panel = make_header_panel("Test Title", "Test Subtitle")
    assert panel is not None
    # Ensure print_banner executes without error
    print_banner(show_subtitle=True)
    print_banner(show_subtitle=False)
    # Ensure show_fullscreen_splash executes without error
    show_fullscreen_splash(animate_progress=False)

