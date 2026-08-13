"""AST and regex-based source and test file scanner."""

import ast
import re
from pathlib import Path

from timmytest.detector.models import Ecosystem, SourceModule, TestFramework, TestModule

IGNORED_DIRS = {
    ".git",
    ".github",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "target",
    "bin",
    "obj",
    "vendor",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".coverage",
    "htmlcov",
    ".idea",
    ".vscode",
    ".turbo",
    ".next",
    ".nuxt",
}

IGNORED_FILES = {
    "__init__.py",
    "conftest.py",
    "setup.py",
    "vite.config.ts",
    "vite.config.js",
    "jest.config.js",
    "vitest.config.ts",
    "tailwind.config.js",
    "postcss.config.js",
}


def _is_test_file(path: Path) -> bool:
    """Determine if a file is a test file."""
    name = path.name.lower()
    parent_names = [p.name.lower() for p in path.parents]

    if (
        "tests" in parent_names
        or "test" in parent_names
        or "__tests__" in parent_names
        or "spec" in parent_names
    ):
        return True

    if (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith(".test.js")
        or name.endswith(".test.ts")
    ):
        return True
    return bool(name.endswith(".spec.js") or name.endswith(".spec.ts") or name.endswith("_test.go"))


def _parse_python_source(file_path: Path) -> tuple[list[str], list[str], int]:
    """Parse a Python source file to extract top-level and method functions and classes."""
    functions: list[str] = []
    classes: list[str] = []
    line_count = 0

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())
        tree = ast.parse(content, filename=str(file_path))

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    functions.append(node.name)
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        not item.name.startswith("_") or item.name == "__init__"
                    ):
                        functions.append(f"{node.name}.{item.name}")
    except Exception:
        pass

    return functions, classes, line_count


def _parse_python_test(file_path: Path) -> list[str]:
    """Extract test functions from a Python test file."""
    test_funcs: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_") or node.name.startswith("test"):
                    test_funcs.append(node.name)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        item.name.startswith("test_") or item.name.startswith("test")
                    ):
                        test_funcs.append(f"{node.name}.{item.name}")
    except Exception:
        pass
    return test_funcs


def _parse_generic_source(file_path: Path) -> tuple[list[str], list[str], int]:
    """Parse JS/TS/Go/Rust using regex heuristics."""
    functions: list[str] = []
    classes: list[str] = []
    line_count = 0

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())

        # JS/TS functions & classes
        func_matches = re.findall(
            r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)|(?:export\s+)?const\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>",
            content,
        )
        for m in func_matches:
            fn_name = m[0] or m[1]
            if fn_name and not fn_name.startswith("_"):
                functions.append(fn_name)

        class_matches = re.findall(r"(?:export\s+)?class\s+([a-zA-Z0-9_$]+)", content)
        for cm in class_matches:
            classes.append(cm)

        # Go functions
        go_funcs = re.findall(r"func\s+([A-Z][a-zA-Z0-9_]*)\s*\(", content)
        functions.extend(go_funcs)

        # Rust functions
        rust_funcs = re.findall(r"pub\s+fn\s+([a-zA-Z0-9_]+)\s*\(", content)
        functions.extend(rust_funcs)
    except Exception:
        pass

    return functions, classes, line_count


def _parse_generic_test(file_path: Path) -> list[str]:
    """Extract test blocks from JS/TS/Go/Rust files."""
    tests: list[str] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        # JS / TS it / test blocks
        js_tests = re.findall(r"(?:it|test)\s*\(\s*['\"]([^'\"]+)['\"]", content)
        tests.extend(js_tests)

        # Go test functions
        go_tests = re.findall(r"func\s+(Test[a-zA-Z0-9_]+)\s*\(", content)
        tests.extend(go_tests)

        # Rust #[test] functions
        rust_tests = re.findall(r"#\[test\][\s\n]+fn\s+([a-zA-Z0-9_]+)", content)
        tests.extend(rust_tests)
    except Exception:
        pass
    return tests


def scan_project_structure(
    root_path: Path,
    ecosystem: Ecosystem,
    framework: TestFramework,
) -> tuple[list[SourceModule], list[TestModule]]:
    """
    Scans the repository to identify source modules and test modules.
    """
    root = root_path.resolve()
    source_modules: list[SourceModule] = []
    test_modules: list[TestModule] = []

    valid_extensions = {".py", ".ts", ".js", ".jsx", ".tsx", ".rs", ".go", ".php", ".rb", ".cs", ".java"}

    for item in root.rglob("*"):
        if not item.is_file():
            continue

        # Check ignored path components
        rel_parts = set(item.relative_to(root).parts)
        if any(ignored in rel_parts for ignored in IGNORED_DIRS):
            continue

        if item.name in IGNORED_FILES or item.suffix not in valid_extensions:
            continue

        rel_path = item.relative_to(root).as_posix()
        is_test = _is_test_file(item)

        if is_test:
            # Parse test file
            test_funcs = _parse_python_test(item) if item.suffix == ".py" else _parse_generic_test(item)

            test_modules.append(
                TestModule(
                    rel_path=rel_path,
                    abs_path=str(item),
                    framework=framework,
                    test_functions=test_funcs,
                    line_count=len(item.read_text(encoding="utf-8", errors="ignore").splitlines()),
                )
            )
        else:
            # Parse source file
            if item.suffix == ".py":
                funcs, classes, lines = _parse_python_source(item)
            else:
                funcs, classes, lines = _parse_generic_source(item)

            lower_name = item.stem.lower()
            is_entry = lower_name in {"main", "app", "cli", "index", "server", "runner"}
            is_util = "util" in lower_name or "helper" in lower_name or "tool" in lower_name
            is_model = "model" in lower_name or "schema" in lower_name or "entity" in lower_name
            is_route = (
                "route" in lower_name
                or "controller" in lower_name
                or "api" in lower_name
                or "view" in lower_name
            )

            source_modules.append(
                SourceModule(
                    rel_path=rel_path,
                    abs_path=str(item),
                    language=item.suffix.lstrip("."),
                    line_count=lines,
                    functions=funcs,
                    classes=classes,
                    is_entrypoint=is_entry,
                    is_utility=is_util,
                    is_model=is_model,
                    is_route=is_route,
                )
            )

    return source_modules, test_modules
