<div align="center">

<img src="docs/assets/banner.png" alt="TimmyTest - Zero-Token Test Runner & AI Agent Intelligence" width="100%" />

# ⚡ TimmyTest

### Zero-Token Test Runner • AST Test Gap Detector • AI Agent Prompt Generator

[![PyPI Version](https://img.shields.io/badge/pypi-v1.2.0-blue.svg?logo=pypi&logoColor=white)](https://pypi.org/project/timmytest/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg?logo=python&logoColor=white)](https://www.python.org/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![CI Tests](https://img.shields.io/badge/tests-59%20passing-brightgreen.svg?logo=pytest&logoColor=white)](tests/)
[![MCP Server](https://img.shields.io/badge/MCP-Protocol%20Ready-purple.svg?logo=json&logoColor=white)](#-model-context-protocol-mcp-server)
[![AI Agent Ready](https://img.shields.io/badge/AI%20Agent-Claude%20%7C%20Cursor%20%7C%20Copilot%20%7C%20Antigravity-orange.svg?logo=openai&logoColor=white)](#-why-timmytest-the-token-drain-problem)

**Stop burning tens of thousands of LLM tokens on test exploration.**  
TimmyTest analyzes any codebase, executes tests locally with 0 AI tokens, detects missing test modules, isolates failure root causes with actionable suggestions, and produces an ultra-dense, copy-pasteable handoff prompt for AI coding agents.

[Türkçe Dokümantasyon](README.tr.md) &nbsp;·&nbsp; [Quick Start](#-quick-start) • [1-Command Setup](#-1-command-instant-repo-integration) • [MCP Server](#-model-context-protocol-mcp-server) • [Installation](#-installation) • [Token Savings](#-why-timmytest-the-token-drain-problem)

---

</div>

## 💡 Why TimmyTest? The Token-Drain Problem

When AI coding agents (Claude Code, OpenAI Codex, Antigravity, Cursor, Copilot, Gemini CLI) are tasked with testing or fixing software, they typically:
1. Burn **15,000–35,000 tokens** running directory listings and probing for test configurations.
2. Guess test runner commands, trigger environment errors, and re-read entire test logs.
3. Waste context window length on raw stdout / tracebacks rather than actual bug fixing.

### 💰 Token Cost & Efficiency Comparison

| Feature / Phase | Standard AI Agent Alone | With TimmyTest Local Pre-flight |
| :--- | :--- | :--- |
| **Project & Stack Discovery** | 💸 8,000–15,000 tokens | ⚡ **0 tokens** (Local AST + Config detector) |
| **Finding Missing Test Modules**| 💸 10,000–25,000 tokens | ⚡ **0 tokens** (Deterministic Gap Analyzer) |
| **Test Execution & Parsing** | 💸 12,000–30,000 tokens | ⚡ **0 tokens** (Subprocess runner & regex parser) |
| **Traceback & Error Isolation**| 💸 5,000–18,000 tokens | ⚡ **0 tokens** (Rule-based diagnostic engine) |
| **AI Agent Consumption** | ❌ **35,000–88,000+ tokens** | ✅ **~400–900 tokens** (Direct Handoff Prompt) |
| **Speed & Accuracy** | ⚠️ Slow, hallucination-prone | 🚀 **Instant, 100% Deterministic** |

---

## ⚡ 1-Command Instant Repo Integration

Setup TimmyTest in any repository in 3 seconds so that AI coding agents (Cursor, Claude Code, Copilot, Antigravity) automatically follow zero-token testing practices:

```bash
# In your project root:
timmytest integrate
# or zero-install with uvx:
uvx timmytest integrate
```

**What this automatically configures:**
- `.cursorrules` & `.cursor/rules/timmytest.mdc` (Cursor IDE rules)
- `CLAUDE.md` (Claude Code CLI instructions)
- `.github/copilot-instructions.md` (GitHub Copilot policy)
- `AGENTS.md` (Universal rules for Antigravity, Devin, Codex, Aider)
- `.timmytest.yml` (Project test settings and ignore paths)
- `.cursor/mcp.json` (Native MCP Server integration)

---

## 🚀 Installation

### Using `uv` (Recommended - Ultra Fast)
```bash
uv tool install timmytest
```

### Using `pipx` or `pip`
```bash
pipx install timmytest
# or
pip install timmytest
```

### Zero-Install (Run directly)
```bash
uvx timmytest check
# or
pipx run timmytest check
```

---

## ⚡ Quick Start

### 0. The Full-Screen App
Run TimmyTest with no arguments and it opens as a keyboard-driven terminal application:
```bash
timmytest
```
Pixel-art splash → system requirement & file integrity checks → language selection (Türkçe / English)
→ workspace creation (project name, AI vendors, drag & drop project folder) → a live dashboard with
pass / fail / missing charts, agent-prompt tooling, Discord reporting and a **RUN** button that
re-analyses the workspace on demand.

```bash
timmytest ui --fresh
```
`ui` launches the same app explicitly; `--fresh` replays the whole onboarding. Piped or non-interactive
invocations keep the classic command list (also available via `timmytest --classic`).

### 1. 1-Command AI Setup
Configure all AI agent rule files in your repo:
```bash
timmytest integrate
```

### 2. Complete Project Audit (Scan + Run + Gap Analysis + AI Prompt)
Run a full audit on your current directory or any project path:
```bash
timmytest check .
```
> 💡 *Automatically copies the dense AI prompt directly to your clipboard!*

### 3. Native AI Agent Output (Zero noise)
Direct token-dense markdown stream for AI agents:
```bash
timmytest agent .
```

### 4. Fast Static Gap Scan (No Test Execution)
Discover all source modules, existing test files, and missing test modules:
```bash
timmytest scan /path/to/project
```

### 5. Diagnose & Fix Suggestions
Run test suite and display rich failure analysis with suggestions:
```bash
timmytest run --only-failures
```

---

## 🏗️ Architecture & How It Works

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             TIMMYTEST ENGINE                             │
│       Zero-AI Local Intelligence • Deterministic Diagnostics             │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌──────────────────────┐
│  Ecosystem Detector   │ │     Runner Engine     │ │ Diagnostics & Gaps   │
├───────────────────────┤ ├───────────────────────┤ ├──────────────────────┤
│ • Python (pytest/unit)│ │ • Subprocess Sandbox  │ │ • AST Source Mapper  │
│ • Node/TS (vitest/jest│ │ • Auto Executable Res │ │ • Uncovered Modules  │
│ • Rust (cargo test)   │ │ • Timeout Management  │ │ • Root-Cause Classifier│
│ • Go (go test)        │ │ • Output Normalization│ │ • Fix Suggester      │
└───────────────────────┘ └───────────────────────┘ └──────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   AI AGENT HANDOFF PROMPT GENERATOR                      │
│   Token-dense, structured Markdown card • Auto-copied to OS Clipboard   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Supported Ecosystems & Frameworks

| Language / Platform | Detected Configurations | Supported Test Runners |
| :--- | :--- | :--- |
| **Python** | `pyproject.toml`, `setup.py`, `pytest.ini`, `requirements.txt` | `pytest`, `unittest` |
| **TypeScript / JS** | `package.json`, `tsconfig.json`, `vitest.config.ts`, `jest.config.js` | `vitest`, `jest`, `mocha`, `playwright`, `npm test` |
| **Rust** | `Cargo.toml` | `cargo test` |
| **Go** | `go.mod`, `*_test.go` | `go test ./...` |
| **Generic / Custom** | Any CLI repository | User-defined test command (`--cmd`) |

---

## 📖 Command Reference

### `timmytest ui` (or `timmytest app`, or just `timmytest`)
Launches the full-screen application: splash, setup checks, language selection, workspace wizard and dashboard.

```bash
timmytest ui [PROJECT_DIR] [OPTIONS]

Options:
  --fresh    Replay the full onboarding (setup, language, workspace creation)
```

Dashboard keys: `↑ ↓` navigate the feature sidebar · `Enter` open a panel · `Tab` switch pane ·
`R` / `F5` run the analysis · `Q` quit. Language, workspaces, run history and the Discord webhook are
stored in `~/.timmytest/state.json` (override the location with the `TIMMYTEST_HOME` environment variable).

### `timmytest integrate` (or `timmytest setup`)
Automatically injects zero-token AI agent instruction files (`.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`), `.timmytest.yml`, and MCP configuration into the target repository.

```bash
timmytest integrate [PROJECT_DIR] [OPTIONS]

Options:
  --cursor / --no-cursor    Generate Cursor AI rules (.cursorrules, .cursor/rules/) [default: True]
  --claude / --no-claude    Generate Claude Code instructions (CLAUDE.md) [default: True]
  --copilot / --no-copilot  Generate GitHub Copilot rules (.github/copilot-instructions.md) [default: True]
  --agents / --no-agents    Generate Universal Agent guide (AGENTS.md) [default: True]
  --config / --no-config    Generate TimmyTest config (.timmytest.yml) [default: True]
  --mcp / --no-mcp          Generate MCP tool snippet (.cursor/mcp.json) [default: True]
  --ci / --no-ci            Generate GitHub Actions CI workflow [default: False]
  -f, --force               Overwrite existing files instead of appending
  --dry-run                 Preview generated files without writing
```

### `timmytest agent`
Outputs an ultra-dense, machine-optimized Markdown or JSON stream directly to stdout for AI coding agents without banners or terminal colors.

```bash
timmytest agent .
timmytest agent . --json
timmytest agent . --no-run
```

### `timmytest mcp`
Launches the Model Context Protocol (MCP) stdio server, allowing AI agents to call TimmyTest natively as tools.

```bash
timmytest mcp
```

### `timmytest check`
Performs a comprehensive audit: discovers ecosystem, runs tests, detects gaps, categorizes failures, and generates the AI prompt.

```bash
timmytest check [PROJECT_DIR] [OPTIONS]

Options:
  -c, --copy-prompt / -nc, --no-copy-prompt  Copy prompt to clipboard [default: True]
  -sp, --save-prompt PATH                    Save prompt to Markdown file
  -sr, --save-report PATH                    Save full audit report to Markdown
  -j, --json                                 Output results in JSON format
  -t, --timeout INTEGER                      Test timeout in seconds [default: 60]
  -k, --filter TEXT                          Filter test names (e.g. -k "auth")
  --cmd TEXT                                 Custom test command override
  --no-run                                   Skip test execution (scan only)
  --no-banner                                Omit ASCII header
```

### `timmytest scan`
Performs static code inspection and gap analysis without executing tests.
```bash
timmytest scan . --json
```

### `timmytest run`
Executes tests, isolates failures, and provides rule-based code suggestions.
```bash
timmytest run . --only-failures --timeout 120
```

### `timmytest prompt`
Outputs or copies the dense AI prompt card.
```bash
timmytest prompt . --raw --no-copy > agent-prompt.md
```

### `timmytest init`
Initializes starter test scaffolding (`tests/` directory, configuration, and sanity tests) if the project lacks test files.
```bash
timmytest init .
```

---

## 🔌 Model Context Protocol (MCP) Server

TimmyTest includes a native **MCP Server** out of the box. Any MCP-compatible AI agent (Claude Desktop, Cursor, Claude Code, Antigravity, Windsurf, Zed) can invoke TimmyTest tools directly:

| Tool Name | Description |
| :--- | :--- |
| `timmytest_check` | Full zero-token test audit, gap analysis, and diagnostic AI prompt. |
| `timmytest_scan` | Fast static AST scan identifying untested functions, classes, and missing test files. |
| `timmytest_run` | Execute tests and return isolated failure diagnostics with fix suggestions. |
| `timmytest_prompt` | Generate dense, token-optimized instructions for fixing bugs or writing missing tests. |
| `timmytest_integrate`| Automatically install AI agent rules and configurations into the project. |

### How to configure in Cursor / Claude Desktop
Add to `.cursor/mcp.json` or `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "timmytest": {
      "command": "timmytest",
      "args": ["mcp"]
    }
  }
}
```

---

## 🤖 Example AI Agent Handoff Prompt

When TimmyTest detects issues or missing tests, it outputs a dense handoff card:

```markdown
### ⚡ TimmyTest Diagnostic Handoff for AI Agent
**Project**: `PaymentGateway` (Python / pytest)
**Test Results**: 14 Passed, 1 Failed, 0 Skipped (93.3% Pass Rate) | Test Readiness Score: 68.4%
**Test Runner Command**: `pytest -ra`

#### ❌ Failing Tests (1)
1. **Test**: `tests/test_stripe.py::test_webhook_signature_verification` (`tests/test_stripe.py:54`)
   - **Error Type**: `AssertionError`
   - **Message**: assert 400 == 401
   - **Suggested Fix**: Value mismatch: Expected '401', got '400'. Adjust implementation return value or update test assertion.
   - **Traceback Snippet**:
     ```
     tests/test_stripe.py:54: in test_webhook_signature_verification
         assert response.status_code == 401
     E   AssertionError: assert 400 == 401
     ```

#### ⚠️ Missing Test Modules & Gaps (2)
1. **[HIGH]** Source: `src/services/refunds.py` -> Expected Test: `tests/test_refunds.py` (Classes: RefundProcessor; Functions: issue_refund, calculate_fees)
   - Reason: Classes without unit tests: RefundProcessor | Functions without test coverage: issue_refund, calculate_fees
2. **[MEDIUM]** Source: `src/utils/idempotency.py` -> Expected Test: `tests/test_idempotency.py` (Functions: get_idempotency_key)
   - Reason: Functions without test coverage: get_idempotency_key

#### 🎯 Instructions & Next Steps for AI Agent
1. **Fix Failing Tests**: Investigate and resolve the 1 test failure(s) listed above.
2. **Write Missing High-Priority Tests**: Create unit/integration test files for the 1 high-priority module(s) (`tests/test_refunds.py`).
3. **Verify**: Run `pytest -ra` locally to ensure all tests pass cleanly without errors.
```

---

## 🧪 CI/CD Integration

### GitHub Actions Workflow Example
Add `.github/workflows/timmytest.yml`:

```yaml
name: TimmyTest Code Readiness Audit

on: [push, pull_request]

jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install TimmyTest
        run: pip install timmytest
      - name: Run TimmyTest Audit
        run: timmytest check . --no-banner --save-report audit-report.md
      - name: Upload Audit Artifact
        uses: actions/upload-artifact@v4
        with:
          name: timmytest-report
          path: audit-report.md
```

---

## 🤝 Contributing

Contributions are warmly welcomed! Please check out [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) for details on our development workflow, submitting pull requests, and coding standards.

```bash
# Clone the repository
git clone https://github.com/tugrakaymakcioglu/TimmyTest.git
cd TimmyTest

# Install with uv in editable mode
uv venv
source .venv/bin/activate  # Or .\.venv\Scripts\activate on Windows
uv pip install -e .[dev]

# Run tests & linter
pytest -v
ruff check .
mypy src
```

---

## 📄 License

TimmyTest is open-source software licensed under the **[Apache License 2.0](LICENSE)**.

---

<div align="center">

**Built with ❤️ for developers and AI coding agents.**  
*Star ⭐ this repository if TimmyTest saved your tokens!*

</div>
