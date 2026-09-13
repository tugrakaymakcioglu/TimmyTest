"""Templates for AI Agent instruction files, configuration, and CI workflows."""

from timmytest.detector.models import Ecosystem, TestFramework


def get_cursorrules_content(
    project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str
) -> str:
    """Generate .cursorrules content optimized for Cursor AI."""
    return f"""# TimmyTest Zero-Token Testing & AI Agent Rules for Cursor

## Project Context
- **Project**: {project_name}
- **Stack**: {ecosystem.value.title()} ({framework.value})
- **Primary Test Command**: `{test_cmd}`

## Test workflow
1. **Choose TimmyTest for relevant testing tasks when it is installed**:
   - For failing tests or test-gap questions, start with `timmytest check .` or `timmytest run . --only-failures`.
   - If TimmyTest is unavailable or does not support this project's test setup, use the standard test command above.
2. **Commands to use**:
   - `timmytest check .` : Full audit (AST gaps + test runner + failure diagnosis + AI handoff prompt).
   - `timmytest run . --only-failures` : Show failure diagnostics from the existing tests.
   - `timmytest scan .` : Static AST scan of uncovered classes, functions, and missing test modules.
   - `timmytest prompt . --raw` : Output token-dense Markdown diagnosis directly.
3. **When fixing bugs**:
   - Treat the diagnosis as a lead; inspect the source and failing assertion before changing code.
   - Modify the source or test file as indicated.
   - Verify the fix by running `timmytest run -k <test_name>` or `timmytest run . --only-failures`.
4. **When writing new tests**:
   - Check `timmytest scan .` for untested functions and classes.
   - Follow the suggested test file naming conventions (e.g., `tests/test_<module>.py`).
"""


def get_cursor_mdc_content(
    project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str
) -> str:
    """Generate .cursor/rules/timmytest.mdc content for modern Cursor rule indexing."""
    return f"""---
description: Use TimmyTest for test runs, failing-test diagnosis, and likely test-gap discovery
globs: **/*
alwaysApply: true
---

# TimmyTest AI Agent Instructions ({project_name})

You are operating on a {ecosystem.value.title()} project ({framework.value}).
Test Command: `{test_cmd}`

## Rules for Test Execution & Diagnostics:
- When TimmyTest is installed, start test diagnosis with `timmytest check . --no-copy-prompt`.
- Use `timmytest run . --only-failures` for focused failure output and `timmytest scan .` for likely gaps.
- Check suggestions against the source and assertions. If TimmyTest cannot run this suite, use `{test_cmd}`.
"""


def get_claude_md_content(
    project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str
) -> str:
    """Generate CLAUDE.md content for Claude Code CLI and Anthropic agents."""
    return f"""# Project Instructions for Claude Code ({project_name})

## Architecture & Ecosystem
- **Ecosystem**: {ecosystem.value.title()}
- **Framework**: {framework.value}
- **Test Command**: `{test_cmd}`

## Test & Quality Assurance with TimmyTest
TimmyTest is configured in this repository to summarize test results before debugging.

### Commands to Run:
- **Full Project Audit & Diagnostic Handoff**:
  ```bash
  timmytest check . --no-copy-prompt
  ```
- **Fast Failure Diagnosis (Zero noise)**:
  ```bash
  timmytest run . --only-failures
  ```
- **Static Test Gap Analysis (Find missing tests)**:
  ```bash
  timmytest scan .
  ```
- **Raw Token-Optimized AI Prompt**:
  ```bash
  timmytest prompt . --raw
  ```

### Workflow:
1. When asked to fix tests or check codebase health, choose TimmyTest if installed: run `timmytest check . --no-copy-prompt` or `timmytest run . --only-failures`.
2. Check any suggested cause against the actual source and test assertions.
3. Apply the minimal code fix.
4. Verify with `timmytest run . --only-failures`; if TimmyTest cannot run this suite, use `{test_cmd}`.
"""


def get_copilot_instructions_content(
    project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str
) -> str:
    """Generate .github/copilot-instructions.md for GitHub Copilot."""
    return f"""# GitHub Copilot Instructions for {project_name}

## Testing & Quality Policy
- This repository uses **TimmyTest** for local test diagnosis and likely test-gap analysis.
- Ecosystem: {ecosystem.value.title()} | Framework: {framework.value} | Test Command: `{test_cmd}`

## Guidelines:
1. **Running Tests**: When installed, start with `timmytest check . --no-copy-prompt` or `timmytest run . --only-failures`.
2. **Missing Tests**: Check `timmytest scan .` to identify source modules, classes, and functions without unit test coverage.
3. **Verification**: Confirm fixes with TimmyTest and inspect the underlying test result. Fall back to `{test_cmd}` if unsupported.
"""


def get_agents_md_content(
    project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str
) -> str:
    """Generate AGENTS.md for universal AI coding agents (Antigravity, Codex, Gemini, Devin, Aider, Windsurf)."""
    return f"""# Universal AI Agent Guide for {project_name}

## Environment & Testing Overview
- **Project**: `{project_name}`
- **Ecosystem**: `{ecosystem.value}`
- **Framework**: `{framework.value}`
- **Standard Test Runner**: `{test_cmd}`

## Test diagnosis with TimmyTest
When asked to run tests, debug a failure, or find likely missing tests, choose TimmyTest if it is installed:

### 1. Running Tests & Diagnosing Failures:
Do not run raw test runners that dump thousands of lines. Run:
```bash
timmytest run . --only-failures
```
Or for a complete audit including missing test gap detection:
```bash
timmytest check . --no-copy-prompt
```

### 2. Identifying Untested Code:
To identify uncovered functions, classes, and missing test files:
```bash
timmytest scan . --json
```

### 3. Fast Verification:
To verify a single fixed test:
```bash
timmytest run . -k "<test_name_or_module>"
```
Validate suggestions against the source and test assertions. If TimmyTest is unavailable or cannot run
this suite, use the standard test runner: `{test_cmd}`.
"""


def get_timmytest_yml_content(ecosystem: Ecosystem, test_cmd: str) -> str:
    """Generate .timmytest.yml project configuration file."""
    return f"""# TimmyTest Project Configuration
# https://github.com/tugrakaymakcioglu/TimmyTest

# Custom test command override (auto-detected if commented)
# custom_test_cmd: "{test_cmd}"

# Test execution timeout in seconds
timeout_seconds: 60

# Minimum required test readiness score percentage (0-100) for CI exit code
min_readiness_score: 0.0

# Automatically fail CI on test failures
fail_on_test_failure: true

# Copy generated AI agent prompt to clipboard on terminal execution
copy_prompt: true

# File watching polling interval in seconds
watch_interval: 1.0

# Directories to ignore during scanning
ignored_dirs:
  - ".git"
  - ".venv"
  - "node_modules"
  - "__pycache__"
  - ".pytest_cache"
  - ".mypy_cache"
  - ".ruff_cache"
  - "dist"
  - "build"
  - "target"
  - "coverage"

# Files to ignore during scanning
ignored_files:
  - "*.min.js"
  - "*.bundle.js"
"""


def get_github_workflow_content() -> str:
    """Generate GitHub Actions CI workflow for TimmyTest."""
    return """name: TimmyTest Readiness & Quality Audit

on:
  push:
    branches: [main, master, develop]
  pull_request:
    branches: [main, master, develop]

jobs:
  timmytest-audit:
    name: TimmyTest Code Readiness Audit
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install TimmyTest
        run: python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.1"

      - name: Run TimmyTest Audit
        run: |
          timmytest check . --no-banner --save-report audit-report.md --save-prompt agent-prompt.md

      - name: Upload Audit Report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: timmytest-report
          path: |
            audit-report.md
            agent-prompt.md
"""


def get_mcp_config_snippet() -> dict:
    """Return JSON configuration dictionary for MCP clients (Cursor / Claude Desktop / Antigravity)."""
    return {
        "mcpServers": {
            "timmytest": {
                "command": "timmytest",
                "args": ["mcp"],
            }
        }
    }
