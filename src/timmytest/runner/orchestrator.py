"""Test execution orchestrator for multi-ecosystem project testing."""

from pathlib import Path

from timmytest.detector.models import Ecosystem, TestFramework, TestRunResult
from timmytest.runner.base import BaseRunner
from timmytest.runner.generic_runner import GenericRunner
from timmytest.runner.go_runner import GoRunner
from timmytest.runner.node_runner import NodeRunner
from timmytest.runner.python_runner import PythonRunner
from timmytest.runner.rust_runner import RustRunner


def _runner_for_ecosystem(ecosystem: Ecosystem) -> BaseRunner:
    """Map an ecosystem to its concrete runner (GenericRunner fallback)."""
    mapping: dict[Ecosystem, type[BaseRunner]] = {
        Ecosystem.PYTHON: PythonRunner,
        Ecosystem.NODE: NodeRunner,
        Ecosystem.RUST: RustRunner,
        Ecosystem.GO: GoRunner,
    }
    return mapping.get(ecosystem, GenericRunner)()


def _route_explicit(
    root: Path,
    ecosystem: Ecosystem,
    framework: TestFramework,
    timeout_seconds: int,
    filter_pattern: str | None,
    test_paths: list[str] | None,
) -> TestRunResult:
    """Route a project whose ecosystem was explicitly detected.

    Explicit detection takes priority over file-based ``can_handle`` sniffing,
    so a polyglot repo (e.g. a Java project that happens to contain a stray
    ``package.json`` or ``pyproject.toml``) is never silently mis-routed to the
    wrong test runner.
    """
    if ecosystem in (Ecosystem.PYTHON, Ecosystem.NODE, Ecosystem.RUST, Ecosystem.GO):
        return _runner_for_ecosystem(ecosystem).run_tests(
            root, None, timeout_seconds, filter_pattern, test_paths=test_paths
        )

    generic = GenericRunner()
    if ecosystem == Ecosystem.JAVA:
        if (root / "gradlew").exists():
            default_cmd = "./gradlew test"
        elif framework == TestFramework.GRADLE:
            default_cmd = "gradle test"
        else:
            default_cmd = "mvn test"
        return generic.run_tests(
            root,
            default_cmd,
            timeout_seconds,
            filter_pattern,
            test_paths,
            ecosystem=ecosystem,
            framework=framework,
        )

    if ecosystem == Ecosystem.DOTNET:
        return generic.run_tests(
            root,
            "dotnet test",
            timeout_seconds,
            filter_pattern,
            test_paths,
            ecosystem=ecosystem,
            framework=framework,
        )

    if ecosystem == Ecosystem.PHP:
        php_cmd = "vendor/bin/phpunit" if (root / "vendor" / "bin" / "phpunit").exists() else "composer test"
        return generic.run_tests(
            root,
            php_cmd,
            timeout_seconds,
            filter_pattern,
            test_paths,
            ecosystem=ecosystem,
            framework=framework,
        )

    if ecosystem == Ecosystem.RUBY:
        return generic.run_tests(
            root,
            "bundle exec rspec",
            timeout_seconds,
            filter_pattern,
            test_paths,
            ecosystem=ecosystem,
            framework=framework,
        )

    return generic.run_tests(
        root,
        "pytest",
        timeout_seconds,
        filter_pattern,
        test_paths,
        ecosystem=Ecosystem.GENERIC,
        framework=TestFramework.CUSTOM,
    )


def run_project_tests(
    root_dir: Path,
    ecosystem: Ecosystem,
    framework: TestFramework,
    custom_cmd: str | None = None,
    timeout_seconds: int = 60,
    filter_pattern: str | None = None,
    test_paths: list[str] | None = None,
) -> TestRunResult:
    """
    Selects the optimal test runner based on ecosystem, executes tests safely,
    and returns a structured TestRunResult.

    Routing precedence:
    1. An explicit ``custom_cmd`` wins over everything else.
    2. An explicitly detected ``ecosystem`` (anything other than UNKNOWN/GENERIC)
       is routed directly to its runner — ``can_handle`` sniffing is NOT used, to
       avoid polyglot-repo mis-routing.
    3. Only when the ecosystem is UNKNOWN/GENERIC do we fall back to sniffing via
       each runner's ``can_handle`` heuristic.
    """
    root = root_dir.resolve()
    explicit = ecosystem not in (Ecosystem.UNKNOWN, Ecosystem.GENERIC)

    if custom_cmd:
        return _runner_for_ecosystem(ecosystem).run_tests(
            root, custom_cmd, timeout_seconds, filter_pattern, test_paths=test_paths
        )

    if explicit:
        return _route_explicit(root, ecosystem, framework, timeout_seconds, filter_pattern, test_paths)

    # Unknown ecosystem: sniff using can_handle heuristics, then fall back.
    for runner_cls in (PythonRunner, NodeRunner, RustRunner, GoRunner):
        runner = runner_cls()
        if runner.can_handle(root):
            return runner.run_tests(root, None, timeout_seconds, filter_pattern, test_paths=test_paths)
    return GenericRunner().run_tests(
        root,
        "pytest",
        timeout_seconds,
        filter_pattern,
        ecosystem=Ecosystem.GENERIC,
        framework=TestFramework.CUSTOM,
    )
