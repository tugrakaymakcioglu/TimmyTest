"""Test execution orchestrator for multi-ecosystem project testing."""

from pathlib import Path

from timmytest.detector.models import Ecosystem, TestFramework, TestRunResult
from timmytest.runner.generic_runner import GenericRunner
from timmytest.runner.go_runner import GoRunner
from timmytest.runner.node_runner import NodeRunner
from timmytest.runner.python_runner import PythonRunner
from timmytest.runner.rust_runner import RustRunner


def run_project_tests(
    root_dir: Path,
    ecosystem: Ecosystem,
    framework: TestFramework,
    custom_cmd: str | None = None,
    timeout_seconds: int = 60,
    filter_pattern: str | None = None,
) -> TestRunResult:
    """
    Selects the optimal test runner based on ecosystem, executes tests safely,
    and returns a structured TestRunResult.
    """
    root = root_dir.resolve()

    if custom_cmd:
        # User supplied explicit custom command
        if ecosystem == Ecosystem.PYTHON:
            return PythonRunner().run_tests(root, custom_cmd, timeout_seconds, filter_pattern)
        elif ecosystem == Ecosystem.NODE:
            return NodeRunner().run_tests(root, custom_cmd, timeout_seconds, filter_pattern)
        elif ecosystem == Ecosystem.RUST:
            return RustRunner().run_tests(root, custom_cmd, timeout_seconds, filter_pattern)
        elif ecosystem == Ecosystem.GO:
            return GoRunner().run_tests(root, custom_cmd, timeout_seconds, filter_pattern)
        else:
            return GenericRunner().run_tests(
                root,
                custom_cmd,
                timeout_seconds,
                filter_pattern,
                ecosystem=ecosystem,
                framework=framework,
            )

    # Automatic runner selection based on ecosystem and project indicators
    if ecosystem == Ecosystem.PYTHON or PythonRunner().can_handle(root):
        return PythonRunner().run_tests(root, None, timeout_seconds, filter_pattern)
    elif ecosystem == Ecosystem.NODE or NodeRunner().can_handle(root):
        return NodeRunner().run_tests(root, None, timeout_seconds, filter_pattern)
    elif ecosystem == Ecosystem.RUST or RustRunner().can_handle(root):
        return RustRunner().run_tests(root, None, timeout_seconds, filter_pattern)
    elif ecosystem == Ecosystem.GO or GoRunner().can_handle(root):
        return GoRunner().run_tests(root, None, timeout_seconds, filter_pattern)

    # Ecosystem-specific runners for Java, .NET, PHP, Ruby
    elif ecosystem == Ecosystem.JAVA:
        default_cmd = "./gradlew test" if (root / "gradlew").exists() else ("gradle test" if framework == TestFramework.GRADLE else "mvn test")
        return GenericRunner().run_tests(root, default_cmd, timeout_seconds, filter_pattern, ecosystem=ecosystem, framework=framework)
    elif ecosystem == Ecosystem.DOTNET:
        return GenericRunner().run_tests(root, "dotnet test", timeout_seconds, filter_pattern, ecosystem=ecosystem, framework=framework)
    elif ecosystem == Ecosystem.PHP:
        php_cmd = "vendor/bin/phpunit" if (root / "vendor" / "bin" / "phpunit").exists() else "composer test"
        return GenericRunner().run_tests(root, php_cmd, timeout_seconds, filter_pattern, ecosystem=ecosystem, framework=framework)
    elif ecosystem == Ecosystem.RUBY:
        return GenericRunner().run_tests(root, "bundle exec rspec", timeout_seconds, filter_pattern, ecosystem=ecosystem, framework=framework)
    else:
        return GenericRunner().run_tests(root, "pytest", timeout_seconds, filter_pattern, ecosystem=Ecosystem.GENERIC, framework=TestFramework.CUSTOM)
