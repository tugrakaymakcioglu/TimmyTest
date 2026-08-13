"""Diagnostics Analyzer for test results."""

from timmytest.detector.models import FailureDetail, TestRunResult
from timmytest.diagnostics.suggester import generate_fix_suggestion


def enrich_test_failures(test_result: TestRunResult) -> TestRunResult:
    """
    Enriches all failures in a TestRunResult with automated fix suggestions.
    """
    enriched_failures: list[FailureDetail] = []

    for failure in test_result.failures:
        if not failure.suggested_fix:
            failure.suggested_fix = generate_fix_suggestion(failure)
        enriched_failures.append(failure)

    test_result.failures = enriched_failures
    return test_result
