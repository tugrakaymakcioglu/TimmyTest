"""Tests for merging the machine-generated registry overlay."""

import copy

import pytest

from timmytest.registry import loader


@pytest.fixture
def base():
    return {
        "version": 1,
        "ecosystems": [
            {
                "id": "python",
                "extensions": [".py"],
                "config_files": ["pyproject.toml"],
                "test_dirs": ["tests"],
                "frameworks": [
                    {
                        "id": "pytest",
                        "default": True,
                        "command": "pytest -ra",
                        "test_patterns": ["test_*.py"],
                    }
                ],
            },
            {
                "id": "node",
                "config_files": ["package.json"],
                "frameworks": [{"id": "vitest", "command": "npx vitest run"}],
            },
        ],
    }


def test_patterns_are_added_to_an_existing_framework(base):
    overlay = {
        "generation": 3,
        "ecosystems": [
            {"id": "python", "frameworks": [{"id": "pytest", "test_patterns": ["*_test.py"]}]}
        ],
    }
    merged = loader.merge_learned(base, overlay)
    pytest_fw = merged["ecosystems"][0]["frameworks"][0]

    assert pytest_fw["test_patterns"] == ["test_*.py", "*_test.py"]
    assert merged["learned_generation"] == 3


def test_merging_does_not_mutate_the_curated_registry(base):
    snapshot = copy.deepcopy(base)
    overlay = {"ecosystems": [{"id": "python", "test_dirs": ["spec"]}]}
    loader.merge_learned(base, overlay)

    assert base == snapshot


def test_the_overlay_can_never_rewrite_a_test_command(base):
    overlay = {
        "ecosystems": [
            {
                "id": "python",
                "frameworks": [{"id": "pytest", "command": "rm -rf /", "default": False}],
            }
        ]
    }
    merged = loader.merge_learned(base, overlay)

    assert merged["ecosystems"][0]["frameworks"][0]["command"] == "pytest -ra"


def test_list_fields_are_extended_without_duplicates(base):
    overlay = {
        "ecosystems": [
            {"id": "python", "config_files": ["pyproject.toml", "hatch.toml"], "test_dirs": ["spec"]}
        ]
    }
    merged = loader.merge_learned(base, overlay)
    python = merged["ecosystems"][0]

    assert python["config_files"] == ["pyproject.toml", "hatch.toml"]
    assert python["test_dirs"] == ["tests", "spec"]


def test_a_new_framework_is_appended_and_never_marked_default(base):
    overlay = {
        "ecosystems": [
            {
                "id": "python",
                "frameworks": [
                    {
                        "id": "nose2",
                        "command": "nose2",
                        "default": True,
                        "test_patterns": ["test_*.py"],
                    }
                ],
            }
        ]
    }
    merged = loader.merge_learned(base, overlay)
    frameworks = merged["ecosystems"][0]["frameworks"]

    assert [f["id"] for f in frameworks] == ["pytest", "nose2"]
    assert "default" not in frameworks[1]


def test_a_new_framework_without_a_command_is_dropped(base):
    overlay = {"ecosystems": [{"id": "python", "frameworks": [{"id": "ghost"}]}]}
    merged = loader.merge_learned(base, overlay)

    assert [f["id"] for f in merged["ecosystems"][0]["frameworks"]] == ["pytest"]


def test_a_learned_ecosystem_lands_after_the_curated_ones(base):
    overlay = {"ecosystems": [{"id": "gleam", "config_files": ["gleam.toml"], "extensions": [".gleam"]}]}
    merged = loader.merge_learned(base, overlay)

    # Detection takes the first match, so appending means a mined ecosystem can
    # only claim projects the curated registry did not.
    assert [e["id"] for e in merged["ecosystems"]] == ["python", "node", "gleam"]


def test_a_learned_ecosystem_without_config_files_is_dropped(base):
    overlay = {"ecosystems": [{"id": "gleam", "extensions": [".gleam"]}]}
    merged = loader.merge_learned(base, overlay)

    assert [e["id"] for e in merged["ecosystems"]] == ["python", "node"]


def test_malformed_overlays_are_ignored(base):
    assert loader.merge_learned(base, {}) is base
    assert loader.merge_learned(base, {"ecosystems": "nope"}) is base
    assert loader.merge_learned(base, {"ecosystems": [{"no_id": 1}, "junk"]})["ecosystems"] == base["ecosystems"]


def test_the_overlay_is_skipped_when_registry_learning_is_off(tmp_path, monkeypatch):
    import json

    from timmytest import flags

    overlay = tmp_path / "learned.yaml"
    overlay.write_text("version: 1\necosystems: []\n", encoding="utf-8")
    monkeypatch.setattr(loader, "_LEARNED_PATH", overlay)

    switch_file = tmp_path / "features.json"
    switch_file.write_text(json.dumps({"features": {"core.registry_learning": False}}), encoding="utf-8")
    monkeypatch.setenv("TIMMYTEST_FLAGS", str(switch_file))
    flags.refresh()

    assert loader._load_learned() is None

    switch_file.write_text(json.dumps({"features": {"core.registry_learning": True}}), encoding="utf-8")
    flags.refresh()
    assert loader._load_learned() == {"version": 1, "ecosystems": []}

    flags.refresh()
