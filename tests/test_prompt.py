"""Tests for AI Agent Prompt Generation."""

from timmytest.detector.models import (
    Ecosystem,
    FailureDetail,
    Priority,
    ProjectInfo,
    TestFramework,
    TestGap,
    TestRunResult,
)
from timmytest.prompt.generator import generate_agent_prompt


def test_generate_agent_prompt():
    proj = ProjectInfo(
        root_dir="/mock/project",
        project_name="OrderService",
        ecosystem=Ecosystem.PYTHON,
        test_framework=TestFramework.PYTEST,
        test_command="pytest -ra",
        test_gaps=[
            TestGap(
                source_module="src/billing.py",
                suggested_test_file="tests/test_billing.py",
                priority=Priority.HIGH,
                reason="Classes without unit tests: BillingManager",
                classes_to_test=["BillingManager"],
            )
        ],
        readiness_score=75.0,
    )

    test_run = TestRunResult(
        ecosystem=Ecosystem.PYTHON,
        framework=TestFramework.PYTEST,
        command="pytest -ra",
        total=5,
        passed=4,
        failed=1,
        failures=[
            FailureDetail(
                test_name="tests/test_orders.py::test_checkout",
                file_path="tests/test_orders.py",
                line_number=35,
                error_type="AssertionError",
                message="assert order.status == 'COMPLETED'",
                suggested_fix="Adjust implementation return value or update test assertion.",
            )
        ],
        has_executed=True,
    )

    prompt = generate_agent_prompt(proj, test_run)

    assert "OrderService" in prompt
    assert "Failing Tests (1)" in prompt
    assert "tests/test_orders.py::test_checkout" in prompt
    assert "tests/test_orders.py:35" in prompt
    assert "Missing Test Modules & Gaps" in prompt
    assert "src/billing.py" in prompt
    assert "tests/test_billing.py" in prompt
    assert "Instructions & Next Steps for AI Agent" in prompt


def _gap(index: int) -> TestGap:
    return TestGap(
        source_module=f"src/module_{index}.py",
        suggested_test_file=f"tests/test_module_{index}.py",
        priority=Priority.HIGH,
        reason="Source file with 40 lines of untested code",
    )


def test_prompt_caps_gap_list_and_says_how_many_were_dropped():
    """An unbounded gap list buries the failures and overruns agent context."""
    proj = ProjectInfo(
        root_dir="/mock",
        project_name="Big",
        ecosystem=Ecosystem.PYTHON,
        test_framework=TestFramework.PYTEST,
        test_command="pytest",
        test_gaps=[_gap(i) for i in range(200)],
    )
    run = TestRunResult(ecosystem=Ecosystem.PYTHON, framework=TestFramework.PYTEST)

    prompt = generate_agent_prompt(proj, run, max_gaps=30)

    assert "Missing Test Modules & Gaps (200)" in prompt
    assert "src/module_29.py" in prompt
    assert "src/module_30.py" not in prompt
    assert "170 more untested module(s)" in prompt


def test_prompt_reports_suite_errors():
    proj = ProjectInfo(
        root_dir="/mock",
        project_name="Suite",
        ecosystem=Ecosystem.NODE,
        test_framework=TestFramework.VITEST,
        test_command="npx vitest run",
    )
    run = TestRunResult(
        ecosystem=Ecosystem.NODE,
        framework=TestFramework.VITEST,
        total=73,
        passed=72,
        errors=1,
        exit_code=1,
        has_executed=True,
    )

    prompt = generate_agent_prompt(proj, run)

    assert "1 Suite Errors" in prompt
