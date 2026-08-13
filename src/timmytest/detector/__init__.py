"""Detector package for TimmyTest."""

from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.gap_analyzer import analyze_test_gaps
from timmytest.detector.models import (
    Ecosystem,
    FailureDetail,
    Priority,
    ProjectAudit,
    ProjectInfo,
    SourceModule,
    TestFramework,
    TestGap,
    TestModule,
    TestRunResult,
    TestStatus,
)
from timmytest.detector.scanner import scan_project_structure

__all__ = [
    "Ecosystem",
    "FailureDetail",
    "Priority",
    "ProjectAudit",
    "ProjectInfo",
    "SourceModule",
    "TestFramework",
    "TestGap",
    "TestModule",
    "TestRunResult",
    "TestStatus",
    "analyze_test_gaps",
    "detect_ecosystem",
    "scan_project_structure",
]
