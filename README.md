# TimmyTest ⚡

> **Zero-token terminal test runner, project test-gap analyzer, and AI agent prompt generator.**

![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)
![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)

---

## 💡 Why TimmyTest?

AI coding agents (Claude Code, OpenAI Codex, Antigravity, Cursor, Copilot, Gemini CLI) waste thousands of tokens discovering project structures, attempting to run test suites, parsing noisy traces, and guessing missing tests.

**TimmyTest** is a 100% local, deterministic CLI tool that:
1. **Discovers**: Automatically detects project ecosystem (Python, JavaScript, TypeScript, Rust, Go) and test runners (`pytest`, `vitest`, `jest`, `cargo test`, `go test`).
2. **Analyzes Gaps**: Scans source modules vs test files to identify untested components and computes a Test Readiness Score.
3. **Runs & Diagnoses**: Executes tests, parses PASS/FAIL statuses, isolates root cause errors, and generates fix suggestions.
4. **Handoff Prompt**: Formats everything into a token-optimized, high-density AI Agent Prompt and copies it straight to your clipboard.

```
+-------------------------------------------------------------------------+
|                              TimmyTest                                  |
|   Zero-AI Intelligence • Gap Detector • Agent Prompt Generator          |
+-------------------------------------------------------------------------+
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
  [ Project Scanner ]      [ Test Executor ]       [ Prompt Builder ]
  - Detects ecosystem      - Runs test suite       - Token-dense prompt
  - Maps source modules    - Parses PASS / FAIL    - Auto-copies to clipboard
  - Finds test gaps        - Analyzes failures     - Ready for Claude/Cursor
```

---

## 🚀 Installation

```bash
# Install with uv (recommended)
uv tool install timmytest

# Or install with pip
pip install timmytest
```

---

## 📖 Commands & Usage

### 1. Complete Audit (`check`)
Runs the full workflow: ecosystem discovery, test execution, test gap analysis, failure diagnosis, suggestions, and AI prompt generation.

```bash
timmytest check
timmytest check /path/to/project --copy-prompt
```

### 2. Fast Static Scan (`scan`)
Scans source files vs existing test files without running tests.

```bash
timmytest scan .
```

### 3. Run & Diagnose Tests (`run`)
Runs existing tests with rich diagnostic output and categorized error suggestions.

```bash
timmytest run . --only-failures
```

### 4. AI Agent Prompt (`prompt`)
Generates the copy-paste prompt formatted for AI coding agents.

```bash
timmytest prompt . --copy
timmytest prompt . --output agent-prompt.md
```

### 5. Initialize Test Scaffolding (`init`)
Bootstraps test folders and configuration if a project has zero tests.

```bash
timmytest init .
```

---

## 🛠️ Supported Ecosystems

| Language / Framework | Supported Runners / Frameworks |
|----------------------|--------------------------------|
| **Python**           | `pytest`, `unittest`           |
| **TypeScript / JS**  | `vitest`, `jest`, `mocha`, `bun test`, `npm test` |
| **Rust**             | `cargo test`                   |
| **Go**               | `go test`                      |
| **Generic / Custom** | User-defined test commands     |

---

## 🤖 Example AI Agent Handoff Prompt

```markdown
### ⚡ TimmyTest Diagnostic Handoff for AI Agent
**Project**: AuthGateway (Python / pytest)
**Status**: 1 Failed, 9 Passed (90% Passing) | Gap: 2 Missing Test Modules (81% Readiness)

#### ❌ Failing Tests (1)
1. `tests/test_auth.py::test_login_invalid_password`
   - **Error**: `AssertionError: assert 403 == 401`
   - **Location**: `tests/test_auth.py:42`
   - **Suggestion**: Update expected HTTP status code to 401 Unauthorized or fix auth service response.

#### ⚠️ Missing Test Modules (2)
1. `[HIGH]` `src/services/tokens.py` -> Missing `tests/test_tokens.py` (Functions: `generate_jwt`, `verify_refresh_token`)
2. `[MEDIUM]` `src/utils/rate_limit.py` -> Missing `tests/test_rate_limit.py` (Functions: `is_rate_limited`)

#### 🎯 Instructions for AI Agent
1. Resolve the failing test in `tests/test_auth.py`.
2. Implement unit tests for `src/services/tokens.py` and `src/utils/rate_limit.py` following existing conventions.
```

---

## 📄 License

Apache-2.0 License. See [LICENSE](LICENSE) for details.
