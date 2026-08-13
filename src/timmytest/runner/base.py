"""Base test runner abstraction."""

from abc import ABC, abstractmethod
from pathlib import Path

from timmytest.detector.models import TestRunResult


class BaseRunner(ABC):
    """Abstract base runner for executing ecosystem-specific tests."""

    @abstractmethod
    def can_handle(self, root_dir: Path) -> bool:
        """Return True if this runner can execute tests in the given project root."""
        pass

    @abstractmethod
    def run_tests(
        self,
        root_dir: Path,
        custom_cmd: str | None = None,
        timeout_seconds: int = 60,
        filter_pattern: str | None = None,
    ) -> TestRunResult:
        """Run the test suite and return structured results."""
        pass
