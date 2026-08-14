# Changelog 📦

All notable changes to **TimmyTest** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.1] - 2026-08-14

### 🛡️ Security & Hardening
- **Zero Command Injection (Eliminated `shell=True`)**: Completely removed `shell=True` across all test runners (`PythonRunner`, `NodeRunner`, `GoRunner`, `RustRunner`, `GenericRunner`) and clipboard utilities. Replaced with structured, sanitized argument lists (`list[str]`) and safe POSIX `shlex` parsing to eliminate arbitrary code execution via `--cmd` or `--filter`.
- **Safe Mode / Dry Run Protection (`--safe / --dry-run`)**: Added `--safe` / `--dry-run` flag to `timmytest check` to allow analyzing untrusted or unfamiliar repositories without executing untrusted test scripts.
- **Process Leak & Timeout Tree Termination**: Integrated safe timeout handling in `execute_safe_subprocess` to cleanly terminate hanging test child processes and prevent orphan zombie processes.

### ⚡ Architecture, Ecosystems & Runners
- **Full Multi-Ecosystem Orchestration**: Added native routing for **Java** (Maven `mvn test` & Gradle `./gradlew test`), **C# / .NET** (`dotnet test`), **PHP** (`vendor/bin/phpunit` / `composer test`), and **Ruby** (`bundle exec rspec`). Projects are no longer erroneously fallen back to pytest.
- **Modern Package Manager Support**: Added auto-detection and execution for `uv` (`uv run pytest`), `poetry` (`poetry run pytest`), `pdm` (`pdm run pytest`), `pipenv`, `pnpm` (`pnpm test`), `yarn` (`yarn test`), `bun` (`bun test`), and `deno` (`deno test`).
- **ANSI Escape Code Sanitization (`strip_ansi`)**: Filtered out all terminal color codes and ANSI escape sequences before regex parsing, preventing Vitest, Jest, and Cargo test output parsing corruption. Enforced `NO_COLOR=1` and `FORCE_COLOR=0`.

### 🧠 AST Intelligence & AI Prompt Optimization
- **Zero-Token AI Signatures & Docstrings**: Enhanced AST parser and prompt generator to extract full function signatures, argument types, return annotations, async flags, and docstrings. AI coding agents (Claude Code, Cursor, Codex, Antigravity) receive dense function context directly in the diagnostic handoff without spending extra tokens reading source files.
- **Multi-Language AST Extraction**: Expanded scanner for TypeScript/JavaScript (typed arrow functions, class methods), Go (struct receiver methods), Rust (`impl` blocks and traits), and Java/C#/PHP/Ruby class/method declarations.
- **False-Positive-Free Gap Correlation**: Eliminated flawed substring matching (e.g. `cat.py` matching `test_category.py`) in `_find_matching_test`. Added AST import verification to ensure test files actually import the target source modules.

### 🛠️ Developer Experience (DX), CI/CD & CLI
- **Continuous Watch Mode (`--watch / -w`)**: Added live file watching to `timmytest check --watch` and `timmytest run --watch` to automatically re-run tests and update gap diagnostics on code changes.
- **CI/CD Exit Code Enforcement & Thresholds (`--fail-under`)**: Propagated non-zero exit codes (exit code `1`) on test failures and added `--fail-under <score>` to enforce minimum test readiness score thresholds in CI pipelines.
- **Smart Test Scaffolding (`init`)**: Upgraded `timmytest init` from creating a dummy test file to generating tailored starter test stubs with functions and mocks for actual discovered test gaps.
- **Project Configuration System (`.timmytest.yml`, `timmytest.toml`, `pyproject.toml`)**: Added `config.py` supporting customized ignored folders, custom test runners, minimum readiness thresholds, and execution timeouts.

---

## [0.1.0] - 2026-08-14

### Added
- **Multi-Ecosystem Detection Engine**: Python (`pytest`, `unittest`), Node/TS (`vitest`, `jest`, `mocha`), Rust (`cargo test`), Go (`go test`).
- **AST Source & Gap Analyzer**: Correlates source modules with test files, assigns priority (`HIGH`, `MEDIUM`, `LOW`), and calculates Test Readiness Score.
- **Deterministic Test Runner**: Executes test suites safely in subprocesses with timeout and capture.
- **Diagnostic Engine**: Rule-based root-cause analysis and actionable fix suggestions for test failures.
- **AI Agent Prompt Generator**: Generates high-density, token-optimized Markdown handoff cards for Claude Code, Codex, Antigravity, and Cursor.
- **Cross-Platform Clipboard Integration**: Supports Windows `clip`, macOS `pbcopy`, Linux `wl-copy`/`xclip`.
- **Rich Terminal UI**: Stylish tables, failure panels, ASCII headers, and progress bars.
- **CLI Commands**: `check`, `scan`, `run`, `prompt`, `init`, `version` with `--json`, `--save-prompt`, `--save-report`, `--filter`, `--timeout` flags.
- **Comprehensive Pytest Suite**: 31 unit and integration tests passing across all components.
