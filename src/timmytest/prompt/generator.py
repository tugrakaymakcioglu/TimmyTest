"""AI Agent Prompt Generator for TimmyTest.

Produces high-density, token-optimized instructions for AI coding agents
such as Claude Code, OpenAI Codex, Antigravity, Cursor, and Copilot with
zero-token signature extraction.
"""

from timmytest.detector.models import Priority, ProjectInfo, TestRunResult

#: A prompt is a working instruction, not a database dump. On a large codebase
#: the unbounded version emitted every gap - hundreds of modules, thousands of
#: lines - which blows past agent context windows and buries the failures the
#: agent is supposed to fix first. Gaps arrive highest-priority first, so the
#: cut always keeps the work that matters.
MAX_PROMPT_GAPS = 30
MAX_PROMPT_FAILURES = 25


def generate_agent_prompt(
    project: ProjectInfo,
    test_run: TestRunResult,
    max_trace_lines: int = 8,
    max_gaps: int = MAX_PROMPT_GAPS,
    max_failures: int = MAX_PROMPT_FAILURES,
) -> str:
    """
    Constructs an ultra-dense, actionable prompt for an AI agent with function signatures
    and test context so the agent doesn't need extra token roundtrips to inspect source files.
    """
    lines: list[str] = []

    # Title & High-level Status
    lines.append("### ⚡ TimmyTest Diagnostic Handoff for AI Agent")
    lines.append(
        f"**Project**: `{project.project_name}` ({project.ecosystem.value.title()} / {project.test_framework.value})"
    )

    if test_run.has_executed:
        pass_rate = round((test_run.passed / test_run.total) * 100, 1) if test_run.total > 0 else 0.0
        error_part = f", {test_run.errors} Suite Errors" if test_run.errors else ""
        lines.append(
            f"**Test Results**: {test_run.passed} Passed, {test_run.failed} Failed{error_part}, "
            f"{test_run.skipped} Skipped "
            f"({pass_rate}% Pass Rate) | Test Readiness Score: {project.readiness_score}%"
        )
    else:
        lines.append(
            f"**Test Status**: Static Scan Only | Test Readiness Score: {project.readiness_score}% "
            f"({len(project.test_modules)} test files, {len(project.test_gaps)} untested modules)"
        )

    lines.append(f"**Test Runner Command**: `{project.test_command or test_run.command or 'pytest'}`")
    lines.append("")

    # Section 1: Failing Tests
    if test_run.failures:
        shown_failures = test_run.failures[:max_failures]
        lines.append(f"#### ❌ Failing Tests ({len(test_run.failures)})")
        for idx, fail in enumerate(shown_failures, start=1):
            location_str = (
                f" (`{fail.file_path}:{fail.line_number}`)" if fail.file_path and fail.line_number else ""
            )
            lines.append(f"{idx}. **Test**: `{fail.test_name}`{location_str}")
            lines.append(f"   - **Error Type**: `{fail.error_type}`")
            lines.append(f"   - **Message**: {fail.message}")
            if fail.suggested_fix:
                lines.append(f"   - **Suggested Fix**: {fail.suggested_fix}")

            # Add short traceback snippet if present
            if fail.traceback:
                tb_lines = [tb_line for tb_line in fail.traceback.splitlines() if tb_line.strip()][
                    -max_trace_lines:
                ]
                lines.append("   - **Traceback Snippet**:")
                lines.append("     ```")
                for tbl in tb_lines:
                    lines.append(f"     {tbl}")
                lines.append("     ```")
        remaining = len(test_run.failures) - len(shown_failures)
        if remaining > 0:
            lines.append(f"_… and {remaining} further failure(s); fix these first, then re-run._")
        lines.append("")
    elif test_run.has_executed and test_run.failed == 0:
        lines.append("#### ✅ Existing Tests: All Passing (0 Failures)")
        lines.append("")

    # Section 2: Missing Test Modules / Test Gaps with Signatures
    if project.test_gaps:
        shown_gaps = project.test_gaps[:max_gaps]
        lines.append(f"#### ⚠️ Missing Test Modules & Gaps ({len(project.test_gaps)})")
        for idx, gap in enumerate(shown_gaps, start=1):
            badge = f"[{gap.priority.value}]"

            lines.append(
                f"{idx}. **{badge}** Source: `{gap.source_module}` -> Expected Test: `{gap.suggested_test_file}`"
            )
            lines.append(f"   - Reason: {gap.reason}")

            if gap.classes_to_test:
                lines.append(f"   - **Classes to Test**: `{', '.join(gap.classes_to_test)}`")

            if gap.function_details:
                lines.append("   - **Functions & Signatures**:")
                for fd in gap.function_details[:5]:
                    sig = fd.signature or "()"
                    doc = f' - "{fd.docstring}"' if fd.docstring else ""
                    prefix = "async " if fd.is_async else ""
                    lines.append(f"     * `{prefix}{fd.name}{sig}`{doc}")
            elif gap.functions_to_test:
                lines.append(f"   - **Functions to Test**: `{', '.join(gap.functions_to_test[:5])}`")

        remaining_gaps = len(project.test_gaps) - len(shown_gaps)
        if remaining_gaps > 0:
            lines.append(
                f"_… and {remaining_gaps} more untested module(s) of lower priority. "
                f"Run `timmytest scan --json` for the full list._"
            )
        lines.append("")

    # Section 3: Direct Action Items for AI Agent
    lines.append("#### 🎯 Instructions & Next Steps for AI Agent")
    step_num = 1
    if test_run.failures:
        lines.append(
            f"{step_num}. **Fix Failing Tests**: Investigate and resolve the {len(test_run.failures)} test failure(s) listed above."
        )
        step_num += 1

    high_gaps = [g for g in project.test_gaps if g.priority == Priority.HIGH]
    if high_gaps:
        lines.append(
            f"{step_num}. **Write Missing High-Priority Tests**: Create unit/integration test files for the {len(high_gaps)} high-priority module(s) (e.g. `{high_gaps[0].suggested_test_file}`)."
        )
        step_num += 1
    elif project.test_gaps:
        lines.append(
            f"{step_num}. **Increase Test Coverage**: Create unit tests for missing modules starting with `{project.test_gaps[0].suggested_test_file}`."
        )
        step_num += 1

    lines.append(
        f"{step_num}. **Verify**: Run `{project.test_command or 'pytest'}` locally to ensure all tests pass cleanly without errors."
    )

    return "\n".join(lines)
