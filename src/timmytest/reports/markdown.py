"""Markdown report generator for TimmyTest."""

from pathlib import Path

from timmytest.detector.models import ProjectAudit


def generate_markdown_report(audit: ProjectAudit, output_path: Path | None = None) -> str:
    """Generates a complete Markdown report of the audit and optionally saves it."""
    proj = audit.project
    tr = audit.test_run

    lines: list[str] = [
        f"# TimmyTest Audit Report: {proj.project_name}",
        "",
        "## 📊 Executive Summary",
        f"- **Ecosystem**: {proj.ecosystem.value.title()}",
        f"- **Test Framework**: {proj.test_framework.value}",
        f"- **Test Readiness Score**: {proj.readiness_score}%",
        f"- **Source Modules Discovered**: {len(proj.source_modules)}",
        f"- **Existing Test Files**: {len(proj.test_modules)}",
        f"- **Untested Module Gaps**: {len(proj.test_gaps)}",
        "",
    ]

    if tr.has_executed:
        lines.extend(
            [
                "## ⚡ Test Execution",
                f"- **Total Tests Executed**: {tr.total}",
                f"- **Passed**: {tr.passed}",
                f"- **Failed**: {tr.failed}",
                f"- **Errors (suite/setup)**: {tr.errors}",
                f"- **Skipped**: {tr.skipped}",
                f"- **Duration**: {tr.duration_seconds}s",
                f"- **Exit Code**: {tr.exit_code}",
                f"- **Command**: `{tr.command}`",
                "",
            ]
        )

        if tr.failures:
            lines.append(f"### ❌ Test Failures ({len(tr.failures)})")
            for idx, fail in enumerate(tr.failures, start=1):
                loc = (
                    f" (`{fail.file_path}:{fail.line_number}`)" if fail.file_path and fail.line_number else ""
                )
                lines.append(f"#### {idx}. `{fail.test_name}`{loc}")
                lines.append(f"- **Error**: `{fail.error_type}` - {fail.message}")
                if fail.suggested_fix:
                    lines.append(f"- **Fix Suggestion**: {fail.suggested_fix}")
                if fail.traceback:
                    lines.append("```")
                    lines.append(fail.traceback)
                    lines.append("```")
                lines.append("")

    if proj.test_gaps:
        lines.append(f"## ⚠️ Test Gaps & Missing Test Modules ({len(proj.test_gaps)})")
        lines.append("| Priority | Source Module | Expected Test File | Reason |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for g in proj.test_gaps:
            lines.append(
                f"| `{g.priority.value}` | `{g.source_module}` | `{g.suggested_test_file}` | {g.reason} |"
            )
        lines.append("")

    lines.extend(
        [
            "## 🤖 AI Agent Handoff Prompt",
            "```markdown",
            audit.agent_prompt,
            "```",
            "",
        ]
    )

    report_text = "\n".join(lines)
    if output_path:
        output_path.write_text(report_text, encoding="utf-8")
    return report_text
