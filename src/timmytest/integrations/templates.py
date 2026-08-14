"""Templates for AI Agent instruction files, configuration, and CI workflows."""

from timmytest.detector.models import Ecosystem, TestFramework


def get_cursorrules_content(project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str) -> str:
    """Generate .cursorrules content optimized for Cursor AI."""
    return f"""# TimmyTest Zero-Token Testing & AI Agent Rules for Cursor

## Project Context
- **Project**: {project_name}
- **Stack**: {ecosystem.value.title()} ({framework.value})
- **Primary Test Command**: `{test_cmd}`

## Critical Agent Guidelines (Token Efficiency)
1. **Never run raw verbose test runners or search entire codebase blindly**:
   - Running raw test suites burns 15,000+ unnecessary LLM tokens on stdout logs and tracebacks.
   - Always use `timmytest check` or `timmytest run --only-failures` to run and diagnose tests.
2. **Commands to use**:
   - `timmytest check .` : Full audit (AST gaps + test runner + failure diagnosis + AI handoff prompt).
   - `timmytest run . --only-failures` : Ultra-fast test execution isolating only failing tests with fix suggestions.
   - `timmytest scan .` : Static AST scan of uncovered classes, functions, and missing test modules.
   - `timmytest prompt . --raw` : Output token-dense Markdown diagnosis directly.
3. **When fixing bugs**:
   - Read the root-cause analysis and suggested fix provided by TimmyTest.
   - Modify the source or test file as indicated.
   - Verify the fix by running `timmytest run -k <test_name>` or `timmytest run . --only-failures`.
4. **When writing new tests**:
   - Check `timmytest scan .` for untested functions and classes.
   - Follow the suggested test file naming conventions (e.g., `tests/test_<module>.py`).
"""


def get_cursor_mdc_content(project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str) -> str:
    """Generate .cursor/rules/timmytest.mdc content for modern Cursor rule indexing."""
    return f"""---
description: Zero-Token Test Running and Diagnostics with TimmyTest
globs: **/*
alwaysApply: true
---

# TimmyTest AI Agent Instructions ({project_name})

You are operating on a {ecosystem.value.title()} project ({framework.value}).
Test Command: `{test_cmd}`

## Rules for Test Execution & Diagnostics:
- DO NOT run raw test commands directly (e.g. `{test_cmd}`) when diagnosing failures or looking for test gaps.
- USE `timmytest check` to run tests and receive structured, zero-token diagnostic handoffs.
- USE `timmytest run --only-failures` for quick verification loops when fixing bugs.
- USE `timmytest scan` to find untested functions and classes without executing code.
- Always trust the root cause isolation and suggested fix provided by TimmyTest.
"""


def get_claude_md_content(project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str) -> str:
    """Generate CLAUDE.md content for Claude Code CLI and Anthropic agents."""
    return f"""# Project Instructions for Claude Code ({project_name})

## Architecture & Ecosystem
- **Ecosystem**: {ecosystem.value.title()}
- **Framework**: {framework.value}
- **Test Command**: `{test_cmd}`

## Test & Quality Assurance with TimmyTest
TimmyTest is configured in this repository to prevent token waste during testing and debugging.

### Commands to Run:
- **Full Project Audit & Diagnostic Handoff**:
  ```bash
  timmytest check .
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
1. When asked to fix tests or check codebase health, run `timmytest check .` or `timmytest run . --only-failures`.
2. Inspect the diagnostic summary (error type, exact line number, and rule-based fix suggestion).
3. Apply the minimal code fix.
4. Verify by running `timmytest run . --only-failures`.
"""


def get_copilot_instructions_content(project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str) -> str:
    """Generate .github/copilot-instructions.md for GitHub Copilot."""
    return f"""# GitHub Copilot Instructions for {project_name}

## Testing & Quality Policy
- This repository uses **TimmyTest** for zero-token test discovery and AST gap analysis.
- Ecosystem: {ecosystem.value.title()} | Framework: {framework.value} | Test Command: `{test_cmd}`

## Guidelines:
1. **Running Tests**: Run `timmytest check .` or `timmytest run . --only-failures`.
2. **Missing Tests**: Check `timmytest scan .` to identify source modules, classes, and functions without unit test coverage.
3. **Verification**: Always confirm fixes with `timmytest run . --only-failures` before committing code.
"""


def get_agents_md_content(project_name: str, ecosystem: Ecosystem, framework: TestFramework, test_cmd: str) -> str:
    """Generate AGENTS.md for universal AI coding agents (Antigravity, Codex, Gemini, Devin, Aider, Windsurf)."""
    return f"""# Universal AI Agent Guide for {project_name}

## Environment & Testing Overview
- **Project**: `{project_name}`
- **Ecosystem**: `{ecosystem.value}`
- **Framework**: `{framework.value}`
- **Standard Test Runner**: `{test_cmd}`

## ⚡ Token-Saving Protocol (TimmyTest)
To prevent wasting LLM context window tokens on test discovery and large traceback outputs:

### 1. Running Tests & Diagnosing Failures:
Do not run raw test runners that dump thousands of lines. Run:
```bash
timmytest run . --only-failures
```
Or for a complete audit including missing test gap detection:
```bash
timmytest check . --raw
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
        run: pip install timmytest

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
