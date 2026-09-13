<div align="center">

<img src="docs/assets/banner.png" alt="TimmyTest — Zero-Token Test Runner & AST Gap Analyzer for AI coding agents" width="100%" />

# ⚡ TimmyTest

### Zero-Token Test Runner • AST Test Gap Analyzer • AI Agent Prompt Generator • MCP Server

**English** · [Türkçe](README.tr.md) · [中文](README.zh-CN.md)

[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue?logo=python&logoColor=white)](https://www.python.org/)
[![CI](https://github.com/tugrakaymakcioglu/TimmyTest/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/tugrakaymakcioglu/TimmyTest/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-213%20passing-brightgreen?logo=pytest&logoColor=white)](tests/)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-protocol%20ready-purple?logo=json&logoColor=white)](#-model-context-protocol-mcp-server)
[![Platforms](https://img.shields.io/badge/OS-Windows%20%7C%20macOS%20%7C%20Linux-blue?logo=windows95&logoColor=white)](#-installation)

**Give your coding agent a useful test report before it starts debugging.**
TimmyTest runs your existing tests locally, identifies likely missing tests and summarizes failures in a
short prompt you can hand to Claude Code, Codex or Cursor. The local scan and test run do not call an AI API;
the handoff prompt still consumes tokens when you send it to an agent.

```bash
python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.1"
timmytest check .
```

Install from GitHub for now. The package is not yet available on PyPI; the `pip install timmytest` and
`uvx timmytest` commands will work only after a PyPI release.

If the first run fails or the report is unclear, [open an issue](https://github.com/tugrakaymakcioglu/TimmyTest/issues/new/choose)
with the command, operating system and a redacted output sample. Real project feedback will guide the next release.

[🚀 Quick Start](#-quick-start) · [🎬 Demo](#-live-demo) · [🤖 AI agent testing guide](https://tugrakaymakcioglu.github.io/TimmyTest/ai-agent-testing.html) · [🔌 MCP Server](#-model-context-protocol-mcp-server) · [📦 Install](#-installation)

</div>

---

## 🎬 Live Demo

Real terminal output — `timmytest check` on a demo Python project with 1 failing test and 1 untested module:

<img src="docs/assets/timmytest-demo.gif" alt="TimmyTest demo: project overview, test results, failure diagnosis with fix suggestion, missing test gaps, and the AI agent handoff prompt" width="100%" />

<details>
<summary><b>📸 Full-resolution stills</b></summary>

| Step | Screenshot |
|:---|:---|
| **Project overview** — ecosystem, framework, readiness score detected in milliseconds | <img src="docs/assets/shot_a.png" width="640" alt="TimmyTest project overview table"/> |
| **Test execution** — 2 tests ran locally: 1 passed, 1 failed, exit code surfaced | <img src="docs/assets/shot_b.png" width="640" alt="TimmyTest test execution results table"/> |
| **Failure diagnosis** — root cause, expected vs actual, and a rule-based fix suggestion | <img src="docs/assets/shot_c.png" width="640" alt="TimmyTest failure diagnostics with suggested fix"/> |
| **Gap analysis** — `src/orchestrator.py` has no test file; HIGH priority, exact path suggested | <img src="docs/assets/shot_d.png" width="640" alt="TimmyTest missing test module gap table"/> |
| **Agent handoff** — the dense prompt your AI receives (auto-copied to clipboard) | <img src="docs/assets/shot_e.png" width="640" alt="TimmyTest AI agent handoff prompt"/> |

</details>

---

## 💡 Why TimmyTest? The Token-Drain Problem

When AI coding agents (Claude Code, OpenAI Codex, Antigravity, Cursor, Copilot, Gemini CLI) are asked to test or fix code, they may:

1. Spend context listing directories and probing for test configs.
2. Guess test runner commands, hit environment errors, and re-read entire test logs.
3. Waste the context window on raw stdout instead of fixing the actual bug.

### What runs locally

| Phase | Without TimmyTest | With TimmyTest preflight |
| :--- | :--- | :--- |
| Project & stack discovery | Agent explores the repo | Local detector summarizes test setup |
| Finding missing test modules | Agent searches source and tests | Local analyzer reports likely gaps |
| Test execution & parsing | Agent reads raw test output | Local runner summarizes results |
| Traceback & error isolation | Agent interprets full tracebacks | Rule-based diagnostics suggest likely causes |
| **Agent handoff** | Raw logs enter the context | A compact prompt enters the context |

Token savings depend on the repository, test output and agent workflow. We have not published a reproducible benchmark yet.

---

## 🚀 Quick Start

### 0. The Full-Screen App
```bash
timmytest
```
Pixel-art splash → system checks → language selection (**Türkçe / English**) → workspace wizard → a live
dashboard with pass/fail/gap charts and a **RUN** button. `timmytest ui --fresh` replays onboarding;
piped/CI invocations keep the classic command list (`--classic`).

### 1. One-command AI setup
```bash
timmytest integrate
```
Generates `.cursorrules`, `CLAUDE.md`, `AGENTS.md`, `.github/copilot-instructions.md`, `.timmytest.yml` and
`.cursor/mcp.json` in the current repo — so your agents follow zero-token testing automatically.

### 2. Complete audit (scan + run + gaps + AI prompt)
```bash
timmytest check .
```
> 💡 *Automatically copies the dense AI prompt to your clipboard.*

### 3. Zero-noise agent output
```bash
timmytest agent .          # dense markdown for AI agents
timmytest agent . --json   # machine-readable JSON
```

### 4. Static gap scan (no execution)
```bash
timmytest scan /path/to/project
```

### 5. Run tests with diagnostics
```bash
timmytest run --only-failures --timeout 120
```

---

## 📦 Installation

```bash
# Current installation from the public GitHub source
python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.1"
timmytest check .
```

PyPI publication is pending. Do not use `pip install timmytest` or `uvx timmytest` until the
[PyPI project page](https://pypi.org/project/timmytest/) is live.

---

## 🏗️ How It Works

```
┌──────────────────────────────────────────────────────────────────────────┐
│                             TIMMYTEST ENGINE                             │
│       Zero-AI Local Intelligence  •  Deterministic Diagnostics           │
└──────────────────────────────────────────────────────────────────────────┘
                                     │
           ┌─────────────────────────┼─────────────────────────┐
           ▼                         ▼                         ▼
┌───────────────────────┐ ┌───────────────────────┐ ┌──────────────────────┐
│  Ecosystem Detector   │ │     Runner Engine     │ │  Diagnostics & Gaps  │
├───────────────────────┤ ├───────────────────────┤ ├──────────────────────┤
│ • 35+ ecosystems      │ │ • Subprocess sandbox  │ │ • AST source mapper  │
│ • Data-driven YAML    │ │ • Auto exec resolve   │ │ • Untested modules   │
│   registry (learned)  │ │ • Process-tree kill   │ │ • Root-cause rules   │
│ • Coverage reports    │ │ • Timeout mgmt        │ │ • Fix suggester      │
└───────────────────────┘ └───────────────────────┘ └──────────────────────┘
                                     │
                                     ▼
┌──────────────────────────────────────────────────────────────────────────┐
│                   AI AGENT HANDOFF PROMPT GENERATOR                      │
│    Token-dense Markdown card  •  Auto-copied to OS clipboard             │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 📖 Supported Ecosystems

TimmyTest ships a **data-driven registry with 35+ ecosystems** (plus a self-learned overlay trained on real GitHub repos):

| Language | Test Runners | | Language | Test Runners |
| :--- | :--- | --- | :--- | :--- |
| **Python** | pytest, unittest | | **PHP** | phpunit |
| **JS/TS** | vitest, jest, mocha, playwright, node --test | | **Ruby** | rspec, minitest |
| **Rust** | cargo test | | **Swift** | xctest |
| **Go** | go test | | **Elixir** | exunit |
| **Java** | junit via maven/gradle | | **Haskell** | hspec |
| **Kotlin** | kotlintest, gradle | | **C/C++** | ctest, gtest |
| **C#/.NET** | dotnet test | | **Lua** | busted |
| **Dart/Flutter** | dart test | | **Perl** | prove |
| **Solidity** | forge, hardhat | | **…and 20+ more** | |

<details>
<summary><b>Smart behaviors baked in</b></summary>

- **Incremental runs**: `--changed` executes only tests affected by uncommitted git changes; `--since main` scopes to a branch.
- **Coverage-aware**: `--coverage` parses `coverage.json` / `cobertura.xml` / `lcov.info` and flags low-coverage files as gaps.
- **Watch mode**: `--watch` re-runs the audit on file change (pruned traversal — no `node_modules` stat storms).
- **CI exit codes**: suite-level errors (unloadable test files) fail CI, not just assertion failures.
- **Safe by default**: no shell, `stdin=DEVNULL`, process-tree kill on timeout, ReDoS-safe scanners.
- **Self-learning registry**: `TimmyTestDev` mines GitHub conventions and widens detection — the shipped wheel keeps improving.

</details>

---

## 🔌 Model Context Protocol (MCP) Server

Any MCP-compatible client (Claude Desktop, Claude Code, Cursor, Antigravity, Windsurf, Zed) can call TimmyTest natively:

| Tool | Description |
| :--- | :--- |
| `timmytest_check` | Full zero-token audit: run tests, gaps, diagnostics, AI prompt. |
| `timmytest_scan` | Static AST scan: untested functions, classes, missing test files. |
| `timmytest_run` | Execute tests, return isolated failures with fix suggestions. |
| `timmytest_prompt` | Generate the dense, token-optimized fix/write-tests prompt. |
| `timmytest_integrate` | Install agent rules + configs into the project. |

```json
{
  "mcpServers": {
    "timmytest": { "command": "timmytest", "args": ["mcp"] }
  }
}
```

---

## 🤖 Example Agent Handoff

```markdown
### ⚡ TimmyTest Diagnostic Handoff for AI Agent
**Project**: `payment-gateway` (Python / pytest)
**Test Results**: 1 Passed, 1 Failed, 0 Skipped (50.0% Pass Rate) | Readiness: 45.0%

#### ❌ Failing Tests (1)
1. **Test**: `test_wrong_fee_expectation` (`tests/test_services.py:10`)
   - **Error Type**: `AssertionError`
   - **Message**: assert 290 == 999 | where 290 = calculate_fees(10000)
   - **Suggested Fix**: Value mismatch: Expected '999', got '290'. Adjust
     implementation return value or update test assertion.

#### ⚠️ Missing Test Modules & Gaps (1)
1. **[HIGH]** Source: `src/orchestrator.py` → Expected Test: `tests/test_orchestrator.py`
   - **Functions & Signatures**:
     * `async JobOrchestrator.submit(self, job_id: str, payload: dict) -> dict` — "Queue a job…"
     * `default_backoff(attempt: int) -> float` — "Exponential backoff with jitter…"

#### 🎯 Instructions & Next Steps for AI Agent
1. **Fix Failing Tests**: resolve the 1 failure above.
2. **Write Missing High-Priority Tests**: create `tests/test_orchestrator.py`.
3. **Verify**: run `pytest -ra` locally until clean.
```

---

## 🧪 CI/CD Integration

```yaml
# .github/workflows/timmytest.yml
name: TimmyTest Audit
on: [push, pull_request]
jobs:
  audit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: python -m pip install "git+https://github.com/tugrakaymakcioglu/TimmyTest.git@v2.0.1"
      - run: timmytest check . --no-banner --save-report audit-report.md
      - uses: actions/upload-artifact@v4
        with: { name: timmytest-report, path: audit-report.md }
```

Gate merges with `--fail-under 60` (readiness %) or rely on the built-in rule:
**any assertion failure or unloadable test file → exit code 1**.

---

## 📚 Documentation

| Doc | Purpose |
| :--- | :--- |
| [Command reference](#-quick-start) | All commands & flags |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Dev setup, test suite, PR workflow |
| [SECURITY.md](SECURITY.md) | Reporting policy |
| [CHANGELOG.md](CHANGELOG.md) | Release history |
| [Landing page](https://tugrakaymakcioglu.github.io/TimmyTest/) | SEO site (this repo) |

---

## 🤝 Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md).

```bash
git clone https://github.com/tugrakaymakcioglu/TimmyTest.git
cd TimmyTest
uv venv && .venv/Scripts/activate    # or source .venv/bin/activate
uv pip install -e .[dev]
python -m pytest -q                  # 213 tests
ruff check . && mypy src
```

---

## 📄 License

Apache License 2.0 — see [LICENSE](LICENSE).

---

<div align="center">

**Built with ❤️ for developers and AI coding agents.**

⭐ **Star this repo if TimmyTest saved your tokens** — it helps others find it.

**English** · [Türkçe](README.tr.md) · [中文](README.zh-CN.md)

</div>
