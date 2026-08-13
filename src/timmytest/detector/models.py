"""Pydantic data models for TimmyTest."""

from enum import StrEnum

from pydantic import BaseModel, Field


class Ecosystem(StrEnum):
    PYTHON = "python"
    NODE = "node"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    DOTNET = "dotnet"
    PHP = "php"
    RUBY = "ruby"
    GENERIC = "generic"
    UNKNOWN = "unknown"


class TestFramework(StrEnum):
    __test__ = False
    PYTEST = "pytest"
    UNITTEST = "unittest"
    VITEST = "vitest"
    JEST = "jest"
    MOCHA = "mocha"
    AVA = "ava"
    PLAYWRIGHT = "playwright"
    CARGO = "cargo"
    GO_TEST = "go_test"
    MAVEN = "maven"
    GRADLE = "gradle"
    DOTNET_TEST = "dotnet_test"
    PHPUNIT = "phpunit"
    RSPEC = "rspec"
    CUSTOM = "custom"
    UNKNOWN = "unknown"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TestStatus(StrEnum):
    __test__ = False
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"
    UNKNOWN = "UNKNOWN"


class SourceModule(BaseModel):
    """Represents a discovered source code file."""

    rel_path: str
    abs_path: str
    language: str
    line_count: int = 0
    functions: list[str] = Field(default_factory=list)
    classes: list[str] = Field(default_factory=list)
    is_entrypoint: bool = False
    is_utility: bool = False
    is_model: bool = False
    is_route: bool = False


class TestModule(BaseModel):
    """Represents an existing test file."""

    __test__ = False
    rel_path: str
    abs_path: str
    framework: TestFramework = TestFramework.UNKNOWN
    test_functions: list[str] = Field(default_factory=list)
    line_count: int = 0


class TestGap(BaseModel):
    """Represents a missing test file or uncovered critical component."""

    __test__ = False
    source_module: str
    suggested_test_file: str
    priority: Priority
    reason: str
    functions_to_test: list[str] = Field(default_factory=list)
    classes_to_test: list[str] = Field(default_factory=list)


class FailureDetail(BaseModel):
    """Detailed information on a single test failure."""

    test_name: str
    file_path: str = ""
    line_number: int | None = None
    error_type: str = "TestFailure"
    message: str = ""
    traceback: str = ""
    suggested_fix: str = ""


class TestRunResult(BaseModel):
    """Summary of executed tests."""

    __test__ = False
    ecosystem: Ecosystem
    framework: TestFramework
    command: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    exit_code: int = 0
    failures: list[FailureDetail] = Field(default_factory=list)
    raw_output: str = ""
    has_executed: bool = False


class ProjectInfo(BaseModel):
    """Metadata about the detected project."""

    root_dir: str
    project_name: str
    ecosystem: Ecosystem
    test_framework: TestFramework
    config_files: list[str] = Field(default_factory=list)
    test_command: str = ""
    source_modules: list[SourceModule] = Field(default_factory=list)
    test_modules: list[TestModule] = Field(default_factory=list)
    test_gaps: list[TestGap] = Field(default_factory=list)
    total_source_files: int = 0
    total_test_files: int = 0
    readiness_score: float = 0.0  # 0 to 100%


class ProjectAudit(BaseModel):
    """Unified audit result containing discovery, execution, gaps, and prompt."""

    project: ProjectInfo
    test_run: TestRunResult
    agent_prompt: str = ""
    summary_markdown: str = ""
