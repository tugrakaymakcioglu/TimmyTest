"""Tests for Typer CLI commands."""

import json
from pathlib import Path

from typer.testing import CliRunner

from timmytest.cli import app

runner = CliRunner()


def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "1.2.0" in result.output


def test_cli_default_invocation():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Tuğra KAYMAKÇIOĞLU" in result.output
    assert "Commands:" in result.output



def test_cli_scan(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(temp_project_dir), "--no-banner"])
    assert result.exit_code == 0
    assert "Project Overview" in result.output
    assert "Missing Test Modules" in result.output


def test_cli_scan_json(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")

    result = runner.invoke(app, ["scan", str(temp_project_dir), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "project" in data
    assert data["project"]["readiness_score"] == 0.0


def test_cli_check_no_run(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    result = runner.invoke(app, ["check", str(temp_project_dir), "--no-run", "--no-banner"])
    assert result.exit_code == 0
    assert "AI Agent Handoff Prompt" in result.output


def test_cli_check_safe_dry_run(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    result = runner.invoke(app, ["check", str(temp_project_dir), "--safe", "--no-banner"])
    assert result.exit_code == 0
    assert "AI Agent Handoff Prompt" in result.output


def test_cli_check_fail_under(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "utils.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    # Readiness score is 0.0%, fail_under is 80.0% -> should exit code 1
    result = runner.invoke(app, ["check", str(temp_project_dir), "--no-run", "--fail-under", "80"])
    assert result.exit_code == 1
    assert "below required threshold" in result.output


def test_cli_init_command(temp_project_dir: Path):
    (temp_project_dir / "pyproject.toml").write_text("[project]\nname='test'\n", encoding="utf-8")

    result = runner.invoke(app, ["init", str(temp_project_dir)])
    assert result.exit_code == 0
    assert (temp_project_dir / "tests" / "conftest.py").exists()
    assert (temp_project_dir / "tests" / "test_example.py").exists()


def test_cli_prompt_raw(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "calc.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    result = runner.invoke(app, ["prompt", str(temp_project_dir), "--no-run", "--raw", "--no-copy"])
    assert result.exit_code == 0
    assert "### ⚡ TimmyTest Diagnostic Handoff for AI Agent" in result.output
