"""Tests for the runtime feature switches read by TimmyTest."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from timmytest import flags
from timmytest.cli import app
from timmytest.tui import features

runner = CliRunner()


@pytest.fixture(autouse=True)
def clean_flag_cache():
    flags.refresh()
    yield
    flags.refresh()


def _write_flags(tmp_path: Path, payload: dict, monkeypatch) -> Path:
    path = tmp_path / "features.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setenv("TIMMYTEST_FLAGS", str(path))
    flags.refresh()
    return path


def test_everything_enabled_without_a_switch_file(tmp_path, monkeypatch):
    monkeypatch.setenv("TIMMYTEST_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("TIMMYTEST_FLAGS", raising=False)
    monkeypatch.chdir(tmp_path)
    flags.refresh()

    assert flags.is_enabled("cli.check")
    assert flags.is_enabled("anything.unknown")
    assert flags.source_path() is None
    assert flags.disabled_keys() == ()


def test_features_map_switches_a_command_off(tmp_path, monkeypatch):
    _write_flags(tmp_path, {"features": {"cli.mcp": False, "cli.scan": True}}, monkeypatch)

    assert flags.is_enabled("cli.mcp") is False
    assert flags.is_enabled("cli.scan") is True
    assert flags.disabled_keys() == ("cli.mcp",)


def test_disabled_list_is_equivalent_to_false(tmp_path, monkeypatch):
    _write_flags(tmp_path, {"disabled": ["core.clipboard"]}, monkeypatch)
    assert flags.is_enabled("core.clipboard") is False


def test_a_corrupt_switch_file_fails_open(tmp_path, monkeypatch):
    path = tmp_path / "features.json"
    path.write_text("{ this is not json", encoding="utf-8")
    monkeypatch.setenv("TIMMYTEST_FLAGS", str(path))
    monkeypatch.setenv("TIMMYTEST_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    flags.refresh()

    # A broken file must never be able to take the tool offline.
    assert flags.is_enabled("cli.check")


def test_project_file_is_consulted_before_the_home_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "features.json").write_text(json.dumps({"features": {"cli.run": False}}), encoding="utf-8")

    project = tmp_path / "project"
    project.mkdir()
    (project / ".timmytest-features.json").write_text(
        json.dumps({"features": {"cli.run": True}}), encoding="utf-8"
    )

    monkeypatch.delenv("TIMMYTEST_FLAGS", raising=False)
    monkeypatch.setenv("TIMMYTEST_HOME", str(home))
    monkeypatch.chdir(project)
    flags.refresh()

    assert flags.is_enabled("cli.run") is True


def test_disabled_command_exits_without_running(tmp_path, monkeypatch):
    _write_flags(tmp_path, {"features": {"cli.scan": False}}, monkeypatch)

    result = runner.invoke(app, ["scan", str(tmp_path), "--no-banner"])
    assert result.exit_code == 2
    assert "cli.scan" in result.output


def test_clipboard_switch_blocks_the_copy(tmp_path, monkeypatch):
    from timmytest.prompt.clipboard import copy_to_clipboard

    _write_flags(tmp_path, {"features": {"core.clipboard": False}}, monkeypatch)
    assert copy_to_clipboard("hello") is False


# --------------------------------------------------------------------------- #
# Sidebar filtering
# --------------------------------------------------------------------------- #


def test_sidebar_hides_switched_off_features(tmp_path, monkeypatch):
    _write_flags(tmp_path, {"features": {"tui.gaps": False}}, monkeypatch)

    keys = {feature.key for feature in features.enabled_features()}
    assert "tui.gaps" not in {features.flag_key(k) for k in keys}
    assert "gaps" not in keys
    assert "overview" in keys


def test_a_group_disappears_once_all_its_features_are_off(tmp_path, monkeypatch):
    discord = next(group for group in features.GROUPS if group.label_key == "grp.discord")
    payload = {"features": {features.flag_key(f.key): False for f in discord.features}}
    _write_flags(tmp_path, payload, monkeypatch)

    labels = {group.label_key for group in features.enabled_groups()}
    assert "grp.discord" not in labels
    assert "grp.overview" in labels


def test_disabling_everything_restores_the_full_sidebar(tmp_path, monkeypatch):
    payload = {"features": {features.flag_key(key): False for key in features.FEATURE_KEYS}}
    _write_flags(tmp_path, payload, monkeypatch)

    # An empty sidebar is a broken app, not a configured one.
    assert features.enabled_groups() == features.GROUPS


def test_default_panel_moves_when_overview_is_off(tmp_path, monkeypatch):
    _write_flags(tmp_path, {"features": {"tui.overview": False}}, monkeypatch)

    assert features.default_feature_key() == "results"
