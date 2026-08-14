"""Project integration installer for TimmyTest and AI Agent rule setup."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.models import Ecosystem, TestFramework
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


@dataclass
class IntegrationResult:
    """Summary of changes performed during integration."""

    created_files: list[Path] = field(default_factory=list)
    modified_files: list[Path] = field(default_factory=list)
    skipped_files: list[Path] = field(default_factory=list)
    ecosystem: Ecosystem = Ecosystem.UNKNOWN
    framework: TestFramework = TestFramework.UNKNOWN


def _write_or_append(
    target_path: Path,
    content: str,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[str, Path]:
    """
    Safely write a new file or append to an existing file.

    Existing files are *never* overwritten (data-loss safety): ``force`` only
    skips the "already integrated" dedup check and re-appends, preserving any
    user-authored content that may already be present.

    Returns status ('created', 'modified', or 'skipped') and the file path.
    """
    if dry_run:
        if target_path.exists():
            return ("modified" if force else "skipped", target_path)
        return ("created", target_path)

    target_path.parent.mkdir(parents=True, exist_ok=True)

    if not target_path.exists():
        target_path.write_text(content, encoding="utf-8")
        return ("created", target_path)

    # File exists: check if timmytest instructions are already present.
    existing_content = target_path.read_text(encoding="utf-8", errors="ignore")
    if ("timmytest" in existing_content.lower() or "timmy test" in existing_content.lower()) and not force:
        return ("skipped", target_path)

    # Append cleanly (never overwrite the user's existing content).
    separator = "\n\n" if existing_content and not existing_content.endswith("\n\n") else ""
    appended = existing_content + separator + content
    target_path.write_text(appended, encoding="utf-8")
    return ("modified", target_path)


def _merge_mcp_config(mcp_path: Path, force: bool = False, dry_run: bool = False) -> tuple[str, Path]:
    """Add TimmyTest to an MCP client config without disturbing the other servers.

    ``.cursor/mcp.json`` is shared: it is where the user registers every MCP
    server they use. Writing our snippet over it would silently unregister all of
    them, so an existing file is loaded, our one entry is merged in, and
    everything else is written back untouched. An unparseable file is left alone
    entirely rather than replaced.
    """
    snippet = get_mcp_config_snippet()

    if not mcp_path.exists():
        if not dry_run:
            mcp_path.parent.mkdir(parents=True, exist_ok=True)
            mcp_path.write_text(json.dumps(snippet, indent=2) + "\n", encoding="utf-8")
        return "created", mcp_path

    try:
        existing = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "skipped", mcp_path
    if not isinstance(existing, dict):
        return "skipped", mcp_path

    servers = existing.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
    if "timmytest" in servers and not force:
        return "skipped", mcp_path

    servers["timmytest"] = snippet["mcpServers"]["timmytest"]
    existing["mcpServers"] = servers
    if not dry_run:
        mcp_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return "modified", mcp_path


def _update_package_json_scripts(package_json_path: Path, dry_run: bool = False) -> bool:
    """Add helper timmytest scripts to package.json if it exists."""
    if not package_json_path.is_file():
        return False

    try:
        data = json.loads(package_json_path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return False

        scripts = data.get("scripts", {})
        changed = False

        if "timmy:check" not in scripts:
            scripts["timmy:check"] = "timmytest check"
            changed = True
        if "timmy:test" not in scripts:
            scripts["timmy:test"] = "timmytest run --only-failures"
            changed = True

        if changed and not dry_run:
            data["scripts"] = scripts
            package_json_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return True
        elif changed and dry_run:
            return True
    except Exception:
        pass

    return False


def integrate_project(
    project_dir: Path,
    include_cursor: bool = True,
    include_claude: bool = True,
    include_copilot: bool = True,
    include_agents: bool = True,
    include_config: bool = True,
    include_ci: bool = False,
    include_mcp: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> IntegrationResult:
    """
    Integrates TimmyTest into the target repository by installing AI agent rules,
    configuration presets, and MCP settings tailored to the project stack.
    """
    root = project_dir.resolve()
    project_name = root.name
    ecosystem, framework, default_cmd, _ = detect_ecosystem(root)
    test_cmd = default_cmd or "pytest"

    result = IntegrationResult(ecosystem=ecosystem, framework=framework)

    def record(status: str, path: Path) -> None:
        if status == "created":
            result.created_files.append(path)
        elif status == "modified":
            result.modified_files.append(path)
        else:
            result.skipped_files.append(path)

    # 1. Cursor rules (.cursorrules & .cursor/rules/timmytest.mdc)
    if include_cursor:
        status, p = _write_or_append(
            root / ".cursorrules",
            get_cursorrules_content(project_name, ecosystem, framework, test_cmd),
            force=force,
            dry_run=dry_run,
        )
        record(status, p)

        status, p = _write_or_append(
            root / ".cursor" / "rules" / "timmytest.mdc",
            get_cursor_mdc_content(project_name, ecosystem, framework, test_cmd),
            force=force,
            dry_run=dry_run,
        )
        record(status, p)

    # 2. Claude Code rules (CLAUDE.md)
    if include_claude:
        status, p = _write_or_append(
            root / "CLAUDE.md",
            get_claude_md_content(project_name, ecosystem, framework, test_cmd),
            force=force,
            dry_run=dry_run,
        )
        record(status, p)

    # 3. GitHub Copilot instructions (.github/copilot-instructions.md)
    if include_copilot:
        status, p = _write_or_append(
            root / ".github" / "copilot-instructions.md",
            get_copilot_instructions_content(project_name, ecosystem, framework, test_cmd),
            force=force,
            dry_run=dry_run,
        )
        record(status, p)

    # 4. Universal AGENTS.md (Antigravity, Codex, Gemini, Devin, Aider, Windsurf)
    if include_agents:
        status, p = _write_or_append(
            root / "AGENTS.md",
            get_agents_md_content(project_name, ecosystem, framework, test_cmd),
            force=force,
            dry_run=dry_run,
        )
        record(status, p)

    # 5. TimmyTest Config (.timmytest.yml)
    # Never regenerated over an existing file, not even with --force: this is
    # where the user keeps ignored_dirs, custom_test_cmd and thresholds, and
    # there is nothing in it TimmyTest could re-derive if it were destroyed.
    if include_config:
        config_path = root / ".timmytest.yml"
        if not config_path.exists():
            if not dry_run:
                config_path.write_text(get_timmytest_yml_content(ecosystem, test_cmd), encoding="utf-8")
            result.created_files.append(config_path)
        else:
            result.skipped_files.append(config_path)

    # 6. Optional MCP configuration (.cursor/mcp.json)
    if include_mcp:
        status, mcp_path = _merge_mcp_config(root / ".cursor" / "mcp.json", force=force, dry_run=dry_run)
        record(status, mcp_path)

    # 7. Optional CI Workflow (.github/workflows/timmytest.yml)
    if include_ci:
        status, p = _write_or_append(
            root / ".github" / "workflows" / "timmytest.yml",
            get_github_workflow_content(),
            force=force,
            dry_run=dry_run,
        )
        record(status, p)

    # 8. Update package.json scripts if Node ecosystem
    if ecosystem == Ecosystem.NODE:
        pkg_json = root / "package.json"
        if _update_package_json_scripts(pkg_json, dry_run=dry_run):
            result.modified_files.append(pkg_json)

    return result
