"""Tests for the full-screen terminal application."""

import asyncio
from pathlib import Path

import pytest

from timmytest.tui import charts, pixelart, preflight
from timmytest.tui.features import ALL_FEATURES, GROUPS, accent_for
from timmytest.tui.i18n import TRANSLATIONS, Translator
from timmytest.tui.state import AppState, RunSnapshot, Workspace, normalise_dropped_path

# --------------------------------------------------------------------------- #
# Pixel art
# --------------------------------------------------------------------------- #


def test_sprites_decode():
    for sprite in (pixelart.timmy_sprite(), pixelart.wordmark_sprite(), pixelart.logo_sprite()):
        assert sprite.width > 20
        assert sprite.height > 20
        assert 0.1 < sprite.aspect < 10


def test_sprite_scales_to_requested_size():
    sprite = pixelart.timmy_sprite()
    grid = sprite.scaled(40, 60)
    assert len(grid) == 60
    assert all(len(row) == 40 for row in grid)
    # The character is opaque in the middle and transparent in the corners.
    assert grid[30][20] is not None
    assert grid[0][0] is None


def test_scaled_results_are_cached():
    sprite = pixelart.wordmark_sprite()
    assert sprite.scaled(30, 20) is sprite.scaled(30, 20)


def test_compose_hero_fills_the_canvas():
    canvas = pixelart.compose_hero(120, 60)
    assert len(canvas) == 60
    assert all(len(row) == 120 for row in canvas)
    painted = sum(1 for row in canvas for pixel in row if pixel is not None)
    assert painted > 120 * 60 * 0.15


def test_compose_hero_survives_tiny_terminals():
    for width, height in [(1, 1), (10, 4), (40, 10)]:
        canvas = pixelart.compose_hero(width, height)
        assert len(canvas) == height
        assert all(len(row) == width for row in canvas)


def test_canvas_renders_one_segment_row_per_two_pixel_rows():
    canvas = pixelart.compose_hero(80, 40)
    rows = pixelart.canvas_to_segments(canvas)
    assert len(rows) == 20
    for row in rows:
        assert sum(len(segment.text) for segment in row) == 80


def test_canvas_to_ansi_emits_truecolor():
    lines = pixelart.canvas_to_ansi(pixelart.compose_hero(60, 20))
    assert len(lines) == 10
    assert any("38;2;" in line for line in lines)


def test_badge_has_stable_dimensions():
    rows = pixelart.badge_segments()
    assert len(rows) == pixelart.BADGE_HEIGHT
    for row in rows:
        assert sum(len(segment.text) for segment in row) == pixelart.BADGE_WIDTH


# --------------------------------------------------------------------------- #
# Dropped path handling
# --------------------------------------------------------------------------- #


def test_normalise_plain_directory(tmp_path: Path):
    assert normalise_dropped_path(str(tmp_path)) == tmp_path.resolve()


def test_normalise_quoted_and_prefixed_paths(tmp_path: Path):
    for raw in (
        f'"{tmp_path}"',
        f"'{tmp_path}'",
        f"& '{tmp_path}'",
        f"cd {tmp_path}",
        f"  {tmp_path}  ",
        f"{tmp_path}\\",
    ):
        assert normalise_dropped_path(raw) == tmp_path.resolve()


def test_dropping_a_file_selects_its_folder(tmp_path: Path):
    dropped = tmp_path / "main.py"
    dropped.write_text("x = 1\n", encoding="utf-8")
    assert normalise_dropped_path(str(dropped)) == tmp_path.resolve()


def test_file_uri_is_understood(tmp_path: Path):
    uri = tmp_path.as_uri()
    assert normalise_dropped_path(uri) == tmp_path.resolve()


def test_missing_and_empty_paths_are_rejected(tmp_path: Path):
    assert normalise_dropped_path("") is None
    assert normalise_dropped_path("   ") is None
    assert normalise_dropped_path(str(tmp_path / "nope")) is None


# --------------------------------------------------------------------------- #
# State
# --------------------------------------------------------------------------- #


@pytest.fixture
def isolated_state(tmp_path, monkeypatch):
    from timmytest.tui import state as state_module

    monkeypatch.setattr(state_module, "APP_DIR", tmp_path / "home")
    monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "home" / "state.json")
    monkeypatch.setattr(state_module, "CACHE_DIR", tmp_path / "home" / "cache")
    return state_module


def test_state_roundtrip(isolated_state, tmp_path):
    state = AppState(language="en", setup_complete=True)
    workspace = Workspace(name="demo", path=str(tmp_path), vendors=["anthropic", "cursor"])
    workspace.record(RunSnapshot(timestamp="2026-01-01T00:00:00+00:00", passed=3, failed=1, missing=2))
    state.add(workspace)
    state.save()

    restored = AppState.load()
    assert restored.language == "en"
    assert restored.setup_complete is True
    assert restored.active_workspace == workspace.id
    assert restored.active is not None
    assert restored.active.vendors == ["anthropic", "cursor"]
    assert restored.active.last_run.passed == 3
    assert len(restored.active.history) == 1


def test_missing_state_file_yields_defaults(isolated_state):
    state = AppState.load()
    assert state.workspaces == []
    assert state.active is None


def test_corrupt_state_file_yields_defaults(isolated_state):
    isolated_state.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    isolated_state.STATE_FILE.write_text("{not json", encoding="utf-8")
    assert AppState.load().workspaces == []


def test_removing_the_active_workspace_picks_another(isolated_state, tmp_path):
    state = AppState()
    first = state.add(Workspace(name="a", path=str(tmp_path)))
    second = state.add(Workspace(name="b", path=str(tmp_path)))
    state.remove(second.id)
    assert state.active_workspace == first.id
    state.remove(first.id)
    assert state.active_workspace is None


def test_history_is_capped(isolated_state, tmp_path):
    from timmytest.tui.state import MAX_HISTORY

    workspace = Workspace(name="a", path=str(tmp_path))
    for index in range(MAX_HISTORY + 15):
        workspace.record(RunSnapshot(timestamp=f"t{index}", passed=index))
    assert len(workspace.history) == MAX_HISTORY
    assert workspace.history[-1].passed == MAX_HISTORY + 14


# --------------------------------------------------------------------------- #
# i18n and features
# --------------------------------------------------------------------------- #


def test_translations_cover_both_languages():
    turkish, english = set(TRANSLATIONS["tr"]), set(TRANSLATIONS["en"])
    assert turkish == english


def test_every_feature_and_group_has_labels():
    for group in GROUPS:
        assert group.label_key in TRANSLATIONS["tr"]
    for feature in ALL_FEATURES:
        assert feature.label_key in TRANSLATIONS["tr"]
        assert feature.label_key in TRANSLATIONS["en"]
        assert accent_for(feature.key).startswith("#")


def test_feature_keys_are_unique():
    keys = [feature.key for feature in ALL_FEATURES]
    assert len(keys) == len(set(keys))


def test_translator_falls_back_to_the_key():
    translator = Translator("tr")
    assert translator("dash.run") == "ÇALIŞTIR"
    translator.set_language("en")
    assert translator("dash.run") == "RUN"
    assert translator("no.such.key") == "no.such.key"
    translator.set_language("klingon")
    assert translator.language == "en"


# --------------------------------------------------------------------------- #
# Preflight
# --------------------------------------------------------------------------- #


def test_system_checks_run_clean():
    results = [check.execute() for check in preflight.system_checks(terminal_size=(200, 50))]
    assert results
    assert all(result.level is not preflight.Level.FAIL for result in results)
    terminal = next(r for r in results if r.key == "terminal")
    assert terminal.detail.startswith("200x50")


def test_integrity_checks_pass_on_a_healthy_install():
    results = [check.execute() for check in preflight.integrity_checks()]
    assert all(result.level is not preflight.Level.FAIL for result in results)


def test_summarise_counts_levels():
    results = [check.execute() for check in preflight.integrity_checks()]
    passed, warned, failed = preflight.summarise(results)
    assert passed + warned + failed == len(results)


def test_a_raising_check_is_reported_not_propagated():
    def boom() -> tuple[preflight.Level, str]:
        raise RuntimeError("kaboom")

    result = preflight.Check("boom", "Boom", boom).execute()
    assert result.level is preflight.Level.FAIL
    assert "kaboom" in result.detail


# --------------------------------------------------------------------------- #
# Charts
# --------------------------------------------------------------------------- #


def test_bars_respect_their_width():
    assert len(charts.hbar(5, 10, 20, charts.PASS).plain) == 20
    assert len(charts.stacked_bar([(1, charts.PASS), (3, charts.FAIL)], 30).plain) == 30
    assert len(charts.hbar(0, 0, 12, charts.PASS).plain) == 12


def test_big_number_is_three_rows():
    assert len(charts.big_number("42", charts.PASS).plain.splitlines()) == 3


def test_gauge_reports_the_percentage():
    assert "77.0%" in charts.gauge(77, 20).plain


def test_history_chart_handles_empty_and_populated_history():
    assert charts.history_chart([]) is not None
    snapshots = [RunSnapshot(timestamp=f"t{i}", passed=i, failed=i % 2) for i in range(6)]
    assert charts.history_chart(snapshots) is not None


# --------------------------------------------------------------------------- #
# The application itself
# --------------------------------------------------------------------------- #


def test_onboarding_reaches_the_workspace_gate(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMMYTEST_HOME", str(tmp_path / "home"))
    from timmytest.tui import state as state_module

    monkeypatch.setattr(state_module, "APP_DIR", tmp_path / "home")
    monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "home" / "state.json")
    monkeypatch.setattr(state_module, "CACHE_DIR", tmp_path / "home" / "cache")

    from timmytest.tui.app import TimmyApp
    from timmytest.tui.screens.language import LanguageScreen
    from timmytest.tui.screens.setup import SetupScreen
    from timmytest.tui.screens.splash import SplashScreen
    from timmytest.tui.screens.workspace import WorkspaceGateScreen

    async def scenario() -> None:
        app = TimmyApp(fresh=True)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause(0.2)
            assert isinstance(app.screen, SplashScreen)

            await pilot.press("escape")
            await pilot.pause(0.2)
            assert isinstance(app.screen, SetupScreen)

            for _ in range(60):
                await asyncio.sleep(0.1)
                if app.screen._finished:
                    break
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert isinstance(app.screen, LanguageScreen)

            await pilot.press("right")
            await pilot.press("enter")
            await pilot.pause(0.2)
            assert app.state.language == "en"

            for _ in range(60):
                await asyncio.sleep(0.1)
                if isinstance(app.screen, WorkspaceGateScreen):
                    break
            assert isinstance(app.screen, WorkspaceGateScreen)
            assert app.state.setup_complete is True
            assert app._exception is None

    asyncio.run(scenario())


def test_workspace_creation_and_every_dashboard_panel(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMMYTEST_HOME", str(tmp_path / "home"))
    from timmytest.tui import state as state_module

    monkeypatch.setattr(state_module, "APP_DIR", tmp_path / "home")
    monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "home" / "state.json")
    monkeypatch.setattr(state_module, "CACHE_DIR", tmp_path / "home" / "cache")

    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "src" / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    (project / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")

    from timmytest.tui.app import TimmyApp
    from timmytest.tui.screens.dashboard import DashboardScreen
    from timmytest.tui.screens.workspace import WorkspaceFormScreen

    async def scenario() -> None:
        app = TimmyApp(fresh=True)
        app.state.setup_complete = True
        async with app.run_test(size=(160, 44)) as pilot:
            await pilot.pause(0.2)
            app.switch_screen(WorkspaceFormScreen())
            await pilot.pause(0.3)

            app.screen.query_one("#form-name").value = "demo"
            app.screen.query_one("#vendor-anthropic").value = True
            app.screen.query_one("#form-path").value = f'"{project}"'
            await pilot.pause(0.4)
            app.screen.query_one("#form-create").press()

            for _ in range(120):
                await asyncio.sleep(0.1)
                if isinstance(app.screen, DashboardScreen):
                    break
            assert isinstance(app.screen, DashboardScreen)
            assert app.state.active is not None
            assert app.state.active.name == "demo"
            assert app.audit is not None
            # The scan must not have executed the target project's test suite.
            assert app.audit.test_run.has_executed is False

            for feature in ALL_FEATURES:
                app.screen.show_panel(feature.key)
                await pilot.pause(0.05)
                assert app._exception is None
            assert app._exception is None

    asyncio.run(scenario())


def test_workspace_form_rejects_incomplete_input(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMMYTEST_HOME", str(tmp_path / "home"))
    from timmytest.tui import state as state_module

    monkeypatch.setattr(state_module, "APP_DIR", tmp_path / "home")
    monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "home" / "state.json")

    from timmytest.tui.app import TimmyApp
    from timmytest.tui.screens.workspace import WorkspaceFormScreen

    async def scenario() -> None:
        app = TimmyApp(fresh=True)
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause(0.2)
            app.switch_screen(WorkspaceFormScreen())
            await pilot.pause(0.3)
            app.screen.query_one("#form-create").press()
            await pilot.pause(0.2)
            assert isinstance(app.screen, WorkspaceFormScreen)
            assert app.state.workspaces == []

    asyncio.run(scenario())


def test_quit_shortcuts_and_buttons(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMMYTEST_HOME", str(tmp_path / "home"))
    from timmytest.tui import state as state_module

    monkeypatch.setattr(state_module, "APP_DIR", tmp_path / "home")
    monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "home" / "state.json")

    from timmytest.tui.app import TimmyApp
    from timmytest.tui.screens.dashboard import DashboardScreen
    from timmytest.tui.screens.language import LanguageScreen
    from timmytest.tui.screens.splash import SplashScreen
    from timmytest.tui.screens.workspace import WorkspaceGateScreen

    # 1. Quit from SplashScreen via 'q'
    async def splash_quit_scenario() -> None:
        app = TimmyApp(fresh=True)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause(0.1)
            assert isinstance(app.screen, SplashScreen)
            await pilot.press("q")
            await pilot.pause(0.1)
            assert app.is_headless or not app.is_running

    asyncio.run(splash_quit_scenario())

    # 2. Quit from LanguageScreen via 'q'
    async def lang_quit_scenario() -> None:
        app = TimmyApp(fresh=True)
        async with app.run_test(size=(120, 30)) as pilot:
            app.switch_screen(LanguageScreen())
            await pilot.pause(0.1)
            assert isinstance(app.screen, LanguageScreen)
            await pilot.press("q")
            await pilot.pause(0.1)
            assert app.is_headless or not app.is_running

    asyncio.run(lang_quit_scenario())

    # 3. Quit from WorkspaceGateScreen via gate-quit button
    async def gate_quit_scenario() -> None:
        app = TimmyApp(fresh=True)
        async with app.run_test(size=(120, 30)) as pilot:
            app.switch_screen(WorkspaceGateScreen())
            await pilot.pause(0.1)
            assert isinstance(app.screen, WorkspaceGateScreen)
            app.screen.query_one("#gate-quit").press()
            await pilot.pause(0.1)
            assert app.is_headless or not app.is_running

    asyncio.run(gate_quit_scenario())

    # 4. Exit workspace from DashboardScreen via dash-quit button (redirects to WorkspaceGateScreen)
    async def dash_exit_ws_scenario() -> None:
        app = TimmyApp(fresh=True)
        async with app.run_test(size=(120, 30)) as pilot:
            app.switch_screen(DashboardScreen())
            await pilot.pause(0.1)
            assert isinstance(app.screen, DashboardScreen)
            app.screen.query_one("#dash-quit").press()
            await pilot.pause(0.1)
            assert isinstance(app.screen, WorkspaceGateScreen)
            assert app.is_running

    asyncio.run(dash_exit_ws_scenario())
