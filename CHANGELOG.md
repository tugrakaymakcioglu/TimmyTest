# Changelog 📦

All notable changes to **TimmyTest** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
