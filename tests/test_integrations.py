"""Tests for TimmyTest integration engine and AI agent rule generator."""

import json
from pathlib import Path

from typer.testing import CliRunner

from timmytest.cli import app
from timmytest.detector.models import Ecosystem, TestFramework
from timmytest.integrations.installer import integrate_project
from timmytest.integrations.templates import (
    get_agents_md_content,
    get_claude_md_content,
    get_copilot_instructions_content,
    get_cursor_mdc_content,
    get_cursorrules_content,
    get_github_workflow_content,
    get_mcp_config_snippet,
    get_timmytest_yml_content,
)

runner = CliRunner()


def test_template_generators():
    cr = get_cursorrules_content("MyProject", Ecosystem.PYTHON, TestFramework.PYTEST, "pytest -ra")
    assert "MyProject" in cr
    assert "pytest -ra" in cr
    assert "timmytest check" in cr

    cmdc = get_cursor_mdc_content("MyProject", Ecosystem.PYTHON, TestFramework.PYTEST, "pytest -ra")
    assert "alwaysApply: true" in cmdc

    claude = get_claude_md_content("MyProject", Ecosystem.NODE, TestFramework.VITEST, "npm run test")
    assert "Claude Code" in claude
    assert "npm run test" in claude

    copilot = get_copilot_instructions_content("MyProject", Ecosystem.RUST, TestFramework.CARGO, "cargo test")
    assert "GitHub Copilot" in copilot
    assert "cargo test" in copilot

    agents = get_agents_md_content("MyProject", Ecosystem.GO, TestFramework.GO_TEST, "go test ./...")
    assert "Universal AI Agent Guide" in agents

    yml = get_timmytest_yml_content(Ecosystem.PYTHON, "pytest -ra")
    assert "timeout_seconds" in yml

    ci = get_github_workflow_content()
    assert "actions/setup-python" in ci

    mcp = get_mcp_config_snippet()
    assert "timmytest" in mcp["mcpServers"]


def test_integrate_project_dry_run(temp_project_dir: Path):
    res = integrate_project(temp_project_dir, dry_run=True)
    assert len(res.created_files) > 0
    # Files should not exist on disk during dry run
    assert not (temp_project_dir / ".cursorrules").exists()


def test_integrate_project_full(temp_project_dir: Path):
    (temp_project_dir / "pyproject.toml").write_text("[project]\nname='test-app'\n", encoding="utf-8")

    res = integrate_project(
        temp_project_dir,
        include_cursor=True,
        include_claude=True,
        include_copilot=True,
        include_agents=True,
        include_config=True,
        include_ci=True,
        include_mcp=True,
    )

    assert len(res.created_files) > 0
    assert (temp_project_dir / ".cursorrules").exists()
    assert (temp_project_dir / ".cursor" / "rules" / "timmytest.mdc").exists()
    assert (temp_project_dir / "CLAUDE.md").exists()
    assert (temp_project_dir / ".github" / "copilot-instructions.md").exists()
    assert (temp_project_dir / "AGENTS.md").exists()
    assert (temp_project_dir / ".timmytest.yml").exists()
    assert (temp_project_dir / ".cursor" / "mcp.json").exists()
    assert (temp_project_dir / ".github" / "workflows" / "timmytest.yml").exists()


def test_integrate_project_skip_existing(temp_project_dir: Path):
    # Pre-populate CLAUDE.md with existing content containing timmytest
    claude_file = temp_project_dir / "CLAUDE.md"
    claude_file.write_text("# Existing Claude instructions with timmytest configured", encoding="utf-8")

    res = integrate_project(temp_project_dir, force=False)
    assert claude_file in res.skipped_files


def test_integrate_project_node_package_json(temp_project_dir: Path):
    pkg_file = temp_project_dir / "package.json"
    pkg_file.write_text(json.dumps({"name": "my-node-app", "scripts": {"build": "tsc"}}), encoding="utf-8")

    res = integrate_project(temp_project_dir)
    data = json.loads(pkg_file.read_text(encoding="utf-8"))

    assert "timmy:check" in data["scripts"]
    assert "timmy:test" in data["scripts"]
    assert pkg_file in res.modified_files


def test_cli_integrate_command(temp_project_dir: Path):
    (temp_project_dir / "pyproject.toml").write_text("[project]\nname='my-pkg'\n", encoding="utf-8")

    result = runner.invoke(app, ["integrate", str(temp_project_dir), "--no-banner"])
    assert result.exit_code == 0
    assert "TimmyTest Integration Summary" in result.output
    assert (temp_project_dir / ".cursorrules").exists()
    assert (temp_project_dir / "CLAUDE.md").exists()
    assert (temp_project_dir / "AGENTS.md").exists()


def test_cli_agent_command(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "maths.py").write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")

    result = runner.invoke(app, ["agent", str(temp_project_dir), "--no-run"])
    assert result.exit_code == 0
    assert "### ⚡ TimmyTest Diagnostic Handoff for AI Agent" in result.output


def test_cli_agent_command_json(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "maths.py").write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")

    result = runner.invoke(app, ["agent", str(temp_project_dir), "--no-run", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "project" in data


def test_integrate_force_never_overwrites_user_content(temp_project_dir: Path):
    """force=True must append, not nuke, pre-existing user-authored rule files."""
    cursor_file = temp_project_dir / ".cursorrules"
    cursor_file.write_text("# My custom rules\nrule: keep-me\n", encoding="utf-8")

    integrate_project(temp_project_dir, include_cursor=True, force=True)

    content = cursor_file.read_text(encoding="utf-8")
    # User content preserved, timmytest content appended (not replacing).
    assert "# My custom rules" in content
    assert "rule: keep-me" in content
    assert "timmytest" in content.lower()
