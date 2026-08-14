# Changelog 📦

All notable changes to **TimmyTest** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

_Nothing yet._

---

## [1.2.0] - 2026-08-14

### 🧠 Self-Improving Detection Registry
- **Learned overlay**: `registry/loader.py` now merges an optional, machine-generated `registry/learned.yaml` on top of the curated `ecosystems.yaml`. Rules in it are mined from real open-source repositories, so TimmyTest's detection gets broader with each release without anyone hand-writing YAML.
- **The overlay can only widen detection.** It adds test-file patterns, test directories, config files and source extensions. It can never rewrite the command your test suite runs under, never mark a mined framework as an ecosystem's default, and a mined ecosystem is always appended *after* the curated ones — so it can only claim projects the curated registry did not already claim.
- Gated by the `core.registry_learning` switch; deleting `learned.yaml` returns detection to the curated registry exactly.

### 🎛️ Feature Switches
- **New `timmytest.flags` module**: TimmyTest reads a JSON switch file — `$TIMMYTEST_FLAGS`, a project-local `.timmytest-features.json`, or `~/.timmytest/features.json` — and every CLI command, four engine features (`core.registry_learning`, `core.coverage`, `core.watch`, `core.clipboard`) and all 31 dashboard panels can be turned off individually.
- Switched-off commands exit with code `2` and name the file responsible; switched-off dashboard panels drop out of the sidebar, and a group that loses every panel disappears with it.
- **Fail-open by design**: a missing, unreadable or corrupt switch file always resolves to "everything on". A configuration mistake cannot take the tool offline.

### 🗑️ Removed
- **`timmytest mine`** and the `timmytest.mining` module. GitHub research is not a testing feature and end users have no use for it; the capability moved to the maintainer's private tooling, which is also where mined evidence is turned into registry rules under review.

### ⛏️ Data-Driven Detection Registry (35 ecosystems)
- **Declarative detection engine**: Replaced the hardcoded `detect_ecosystem()` if/else chain with a single `registry/ecosystems.yaml` source of truth plus a small signal engine (`registry/loader.py`). Adding a language now means editing YAML only — no Python changes.
- **35 ecosystems total**: Python, Node/TS, Rust, Go, Java, Kotlin, Scala, .NET, PHP, Ruby, Swift, Dart, Elixir, Haskell, C, C++, Lua, Perl, Zig, Crystal, Clojure, Solidity, Shell/Bash, SQL/dbt, Terraform, PowerShell, R, Julia, Groovy, Erlang, Nim, OCaml, Elm, D, and V — covering the languages vibe-coding agents (Claude Code, Cursor, Codex) produce most.
- **Signal engine** supports `config_files` (incl. recursive globs), `dependency_in`, `script_contains`, `config_content`, `requires_extensions` (for C-vs-C++ / Solidity-vs-Node disambiguation), and command variants with `{runner}`/`{pm}` package-manager placeholders.
- Scanner source extensions and test-file patterns expanded to cover all new languages.

### 🐛 Full-Codebase Audit Fixes
- **Projects under a directory named `test/` were reported as fully tested.** `_is_test_file` walked *every* ancestor of a file, so a checkout at `C:\dev\test\myapp` classified all of its source files as tests — zero source modules, zero gaps, and a perfect readiness score. The directory-name check is now bounded to the project root.
- **LCOV reports with checksums crashed.** `DA:<line>,<hits>,<checksum>` is standard (`lcov --checksum`, genhtml); the parser read everything after the first comma as the hit count and raised `ValueError`. It now reads the second field.
- **LCOV overall coverage was the mean of the per-file percentages**, so a one-line file at 0% cancelled out a thousand-line file at 100% (reported 50% where the truth was 99.9%). It is now total lines hit over total lines found.
- **A malformed, stale or missing coverage report crashed the whole run** with an unhandled `JSONDecodeError` / `FileNotFoundError`. Coverage is an optional input: an unreadable report now costs the coverage panel, not the audit.
- **Cobertura XML declaring entities is refused.** ElementTree expands them, so a few hundred bytes of hostile `coverage.xml` could expand to gigabytes ("billion laughs") while analysing an untrusted repository.
- **`integrate --force` destroyed user-owned files.** It regenerated `.timmytest.yml` over the user's `ignored_dirs`/`custom_test_cmd`, and overwrote `.cursor/mcp.json` — unregistering every *other* MCP server they had configured. The config is now never regenerated, and the MCP config is merged entry-by-entry. This closes the gap left by the 1.2.0 data-loss fix, which only covered `.cursorrules`/`CLAUDE.md`/`AGENTS.md`.
- **Custom test commands were mangled on Windows.** POSIX-mode splitting treats `\` as an escape, turning `C:\tools\pytest.exe` into `C:toolspytest.exe`. Command splitting is now platform-correct, and targeted test paths are passed as argv entries so paths containing spaces survive.
- **`timeout_seconds` in `.timmytest.yml` was dead config** — the CLI's own default of 60 always won. `--timeout` now defaults to unset, so the precedence is flag → config → 60.
- **`--changed` / `--since` were silently ignored for Java, .NET, PHP, Ruby and generic projects**: the selected test paths never reached the runner, so a full suite ran while the output claimed an incremental one.
- **Test correlation matched far too loosely.** A single `from myapp.utils import x` in one test marked *every* `utils.py` in the repository as covered, and a fixture such as `tests/helpers.py` counted as the test suite for `src/helpers.py`. Import matching now verifies the module's directory chain, and files with neither a test-shaped name nor any test functions are no longer accepted as suites.
- **MCP tools ignored the feature switches**, so an agent could run a capability that had been turned off on the CLI. Each tool now honours the matching switch.
- `timmytest init` no longer walks `node_modules` to decide whether a project is TypeScript.

### 🛡️ Audit Fixes (bug / logic / security)
- **No fabricated test counts**: `GenericRunner` (Maven/Gradle/.NET/PHP/Ruby) previously reported a hardcoded `1 passed / 1 total` for any successful command. It now reports counts honestly (0/0) and only signals failure via exit code, since it cannot reliably parse those runners' output.
- **Process-tree termination on timeout**: `execute_safe_subprocess` previously called only `proc.kill()`, leaving grandchildren orphaned on timeout (contradicting the 1.1.1 "tree termination" claim). It now terminates the full tree cross-platform — `taskkill /F /T` on Windows, `killpg` on a detached process group on POSIX.
- **Data-loss safety in `integrate --force`**: `force` used to *overwrite* existing `.cursorrules`/`CLAUDE.md`/`AGENTS.md` with TimmyTest-only content, destroying user-authored rules. It now always appends; `force` only skips the "already integrated" dedup check.
- **Java/Gradle command correctness**: Gradle projects now emit `./gradlew test` only when the wrapper is present, falling back to `gradle test` otherwise (restoring behavior the registry had dropped).

### 🧪 Coverage-Aware Analysis
- **Coverage Report Parsing (`--coverage`)**: Added native parsing for **coverage.py JSON** (`coverage.json`), **Cobertura XML** (`coverage.xml` / `cobertura.xml`), and **LCOV** (`lcov.info`) tracefiles. Overall line coverage and a per-file breakdown are surfaced in a new coverage summary panel, and files below `--coverage-threshold` (default 60%) are appended as MEDIUM-priority remediation gaps.
- **Auto-Discovery**: `--coverage` auto-detects a coverage report in the project root; `--coverage-file <path>` targets an explicit report. `--coverage-threshold <n>` customizes the low-coverage flag threshold.

### ⚡ Incremental Test Selection
- **`--changed` / `--since <ref>`**: Run only the tests affected by recent changes. Uses `git diff` (plus untracked files) to find changed source/test files, correlates them to their test files via the same AST-aware matching used by gap analysis, and passes the targeted test paths to the runner. Example: `timmytest run --changed`, `timmytest check --since main`.

### 🛡️ Correctness & Bug Fixes
- **Polyglot-Repo Routing Fix**: Explicitly detected ecosystems now take priority over `can_handle` file sniffing. A Java project that happens to contain a stray `package.json` or `pyproject.toml` is no longer silently mis-routed to the Node/Python runner.
- **Flaky TUI Focus Race**: Fixed a `NoMatches` race in `WorkspaceGateScreen.on_mount` where the `#gate-create` button could be queried before it was mounted during fast screen transitions.
- **CLI Consistency**: `--no-banner` is now accepted uniformly across all subcommands (including `version`, `prompt`, `init`, and `agent`).

### 🧠 Node.js `node:test` Support
- **TAP Output Parsing**: `NodeRunner` now parses the built-in `node --test` / TAP output (`# pass`, `# fail`, `# skipped`, `# todo`, `not ok N - …`), so zero-dependency Node projects using `node:test` are reported accurately without requiring Jest or Vitest.

### 🧪 Test Infrastructure
- **Real End-to-End Runner Tests**: Added subprocess E2E tests that execute actual Go (`go test`) and Node (`node --test`) projects through the runners — validating output parsing against real toolchains, not mocks. Skipped gracefully when the toolchain is unavailable.
- Test suite grew to **112 passing tests**; `ruff` and `mypy` both clean.

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
