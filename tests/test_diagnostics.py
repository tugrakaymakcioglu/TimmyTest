"""Tests for diagnostic fix suggestions."""

from timmytest.detector.models import FailureDetail
from timmytest.diagnostics.suggester import generate_fix_suggestion


def test_suggestion_for_assertion_equality():
    failure = FailureDetail(
        test_name="test_sum",
        error_type="AssertionError",
        message="assert 10 == 15",
    )
    sug = generate_fix_suggestion(failure)
    assert "Value mismatch" in sug
    assert "15" in sug


def test_suggestion_for_missing_module():
    failure = FailureDetail(
        test_name="test_import",
        error_type="ModuleNotFoundError",
        message="No module named 'fastapi'",
    )
    sug = generate_fix_suggestion(failure)
    assert "Missing dependency 'fastapi'" in sug


def test_suggestion_for_attribute_error_nonetype():
    failure = FailureDetail(
        test_name="test_user",
        error_type="AttributeError",
        message="'NoneType' object has no attribute 'email'",
    )
    sug = generate_fix_suggestion(failure)
    assert "NoneType error" in sug


def test_suggestion_for_type_error_missing_args():
    failure = FailureDetail(
        test_name="test_call",
        error_type="TypeError",
        message="missing 1 required positional argument: 'token'",
    )
    sug = generate_fix_suggestion(failure)
    assert "Mismatched arguments" in sug


def test_suggestion_for_key_error():
    failure = FailureDetail(
        test_name="test_dict",
        error_type="KeyError",
        message="KeyError: 'user_id'",
    )
    sug = generate_fix_suggestion(failure)
    assert "KeyError" in sug
    assert "user_id" in sug


def test_enrich_test_failures():
    from timmytest.detector.models import Ecosystem, TestFramework, TestRunResult
    from timmytest.diagnostics.analyzer import enrich_test_failures

    run_result = TestRunResult(
        ecosystem=Ecosystem.PYTHON,
        framework=TestFramework.PYTEST,
        total=1,
        failed=1,
        failures=[
            FailureDetail(
                test_name="test_bad",
                error_type="KeyError",
                message="KeyError: 'token'",
            )
        ],
    )
    enriched = enrich_test_failures(run_result)
    assert len(enriched.failures) == 1
    assert "KeyError" in enriched.failures[0].suggested_fix

