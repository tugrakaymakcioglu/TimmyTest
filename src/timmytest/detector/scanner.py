"""AST and regex-based source and test file scanner with multi-language AST extraction."""

import ast
import re
from pathlib import Path

from timmytest.detector.models import (
    Ecosystem,
    FunctionDetail,
    SourceModule,
    TestFramework,
    TestModule,
)

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


TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs"}


def _is_test_file(path: Path, root: Path | None = None) -> bool:
    """Determine if a file is a test file.

    ``root`` bounds the directory-name check to the project. Without it, every
    ancestor up to the filesystem root is inspected, so a project that merely
    *lives* under a folder called ``test`` (``C:\\dev\\test\\myapp``) would have
    every one of its source files classified as a test - reporting zero source
    modules, zero gaps, and a perfect readiness score.
    """
    name = path.name.lower()

    if root is not None:
        try:
            relative_parts = path.resolve().relative_to(root.resolve()).parts[:-1]
        except (ValueError, OSError):
            relative_parts = path.parts[:-1]
        parent_names = [part.lower() for part in relative_parts]
    else:
        parent_names = [p.name.lower() for p in path.parents]

    if any(part in TEST_DIR_NAMES for part in parent_names):
        return True

    return bool(
        name.startswith("test_")
        or name.startswith("test-")
        or name.endswith("_test.py")
        or name.endswith(".test.js")
        or name.endswith(".test.ts")
        or name.endswith(".test.jsx")
        or name.endswith(".test.tsx")
        or name.endswith(".spec.js")
        or name.endswith(".spec.ts")
        or name.endswith(".spec.jsx")
        or name.endswith(".spec.tsx")
        or name.endswith("_test.go")
        or name.endswith("_test.rs")
        or name.endswith("test.php")
        or name.endswith("_spec.rb")
        or name.endswith("test.cs")
        or name.endswith("test.java")
        # Kotlin / Scala / Swift / Dart / Elixir / Haskell
        or name.endswith("Test.kt")
        or name.endswith("Tests.kt")
        or name.endswith("Spec.scala")
        or name.endswith("Suite.scala")
        or name.endswith("Test.scala")
        or name.endswith("Tests.swift")
        or name.endswith("Test.swift")
        or name.endswith("_test.dart")
        or name.endswith("_test.exs")
        or name.endswith("Spec.hs")
        or name.endswith("Test.hs")
        # C / C++
        or name.endswith("_test.c")
        or name.endswith("_test.cpp")
        or name.endswith("_test.cc")
        or name.endswith("Test.cpp")
        or name.endswith("Test.cc")
        # Lua / Crystal / Clojure
        or name.endswith("_spec.lua")
        or name.endswith("_spec.cr")
        or name.endswith("_test.clj")
        or name.endswith("_test.cljs")
        # Shell / PowerShell / Groovy / SQL / Terraform
        or name.endswith(".bats")
        or name.endswith(".tests.ps1")
        or name.endswith("_test.ps1")
        or name.endswith("spec.groovy")
        or name.endswith("test.groovy")
        or name.endswith("_test.sql")
        or name.endswith(".tftest.hcl")
        # Solidity (Foundry `*.t.sol`) / Elm
        or name.endswith(".t.sol")
        or name.endswith("test.elm")
        or name.endswith("tests.elm")
        # Erlang / OCaml / Nim / D / V
        or name.endswith("_tests.erl")
        or name.endswith("_test.erl")
        or name.endswith("_test.ml")
        or name.endswith("_test.nim")
        or name.endswith("_test.jl")
        or name.endswith("_test.d")
        or name.endswith("_test.v")
        # Perl (`.t` test files)
        or name.endswith(".t")
    )


def _format_python_args(args_node: ast.arguments) -> str:
    """Formats AST arguments node into readable signature string."""
    parts: list[str] = []
    for arg in args_node.args:
        ann = f": {ast.unparse(arg.annotation)}" if arg.annotation else ""
        parts.append(f"{arg.arg}{ann}")
    if args_node.vararg:
        parts.append(f"*{args_node.vararg.arg}")
    for kwarg in args_node.kwonlyargs:
        ann = f": {ast.unparse(kwarg.annotation)}" if kwarg.annotation else ""
        parts.append(f"{kwarg.arg}{ann}")
    if args_node.kwarg:
        parts.append(f"**{args_node.kwarg.arg}")
    return f"({', '.join(parts)})"


def _parse_python_source(
    file_path: Path,
) -> tuple[list[str], list[FunctionDetail], list[str], list[str], int]:
    """
    Parse Python source file to extract functions with signatures, docstrings, classes, and imports.
    """
    func_names: list[str] = []
    func_details: list[FunctionDetail] = []
    classes: list[str] = []
    imports: list[str] = []
    line_count = 0

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())
        tree = ast.parse(content, filename=str(file_path))

        for node in tree.body:
            # Imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

            # Top-level Functions
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    sig_args = _format_python_args(node.args)
                    ret_ann = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                    sig = f"{sig_args}{ret_ann}"
                    doc = ast.get_docstring(node) or ""
                    first_doc_line = doc.strip().splitlines()[0] if doc.strip() else ""

                    func_names.append(node.name)
                    func_details.append(
                        FunctionDetail(
                            name=node.name,
                            signature=sig,
                            docstring=first_doc_line,
                            is_async=isinstance(node, ast.AsyncFunctionDef),
                            is_method=False,
                            line_number=node.lineno,
                        )
                    )

            # Classes
            elif isinstance(node, ast.ClassDef):
                classes.append(node.name)
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        not item.name.startswith("_") or item.name == "__init__"
                    ):
                        full_name = f"{node.name}.{item.name}"
                        sig_args = _format_python_args(item.args)
                        ret_ann = f" -> {ast.unparse(item.returns)}" if item.returns else ""
                        sig = f"{sig_args}{ret_ann}"
                        doc = ast.get_docstring(item) or ""
                        first_doc_line = doc.strip().splitlines()[0] if doc.strip() else ""

                        func_names.append(full_name)
                        func_details.append(
                            FunctionDetail(
                                name=full_name,
                                signature=sig,
                                docstring=first_doc_line,
                                is_async=isinstance(item, ast.AsyncFunctionDef),
                                is_method=True,
                                line_number=item.lineno,
                            )
                        )
    except Exception:
        pass

    return func_names, func_details, classes, imports, line_count


def _parse_python_test(file_path: Path) -> tuple[list[str], list[str]]:
    """Extract test functions and imported modules from a Python test file."""
    test_funcs: list[str] = []
    imports: list[str] = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(content, filename=str(file_path))
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.append(node.module)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("test_") or node.name == "test":
                    test_funcs.append(node.name)
            elif isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        item.name.startswith("test_") or item.name == "test"
                    ):
                        test_funcs.append(f"{node.name}.{item.name}")
    except Exception:
        pass
    return test_funcs, imports


def _parse_generic_source(
    file_path: Path,
) -> tuple[list[str], list[FunctionDetail], list[str], list[str], int]:
    """Parse JS/TS/Go/Rust/Java/C#/PHP/Ruby source files."""
    functions: list[str] = []
    details: list[FunctionDetail] = []
    classes: list[str] = []
    imports: list[str] = []
    line_count = 0

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        line_count = len(content.splitlines())

        # 1. Imports extraction
        import_matches = re.findall(
            r"""(?:import\s+(?:.*?from\s+)?['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)|use\s+([a-zA-Z0-9_:\\]+);)""",
            content,
        )
        for m in import_matches:
            imp = m[0] or m[1] or m[2]
            if imp:
                imports.append(imp)

        # 2. JS / TS functions & classes
        js_func_matches = re.finditer(
            r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)|(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?(?:\(([^)]*)\)|[a-zA-Z0-9_$]+)(?:\s*:\s*[^=]+)?\s*=>",
            content,
        )
        for m in js_func_matches:
            fn_name = m.group(1) or m.group(3)
            fn_args = m.group(2) or m.group(4) or ""
            if fn_name and not fn_name.startswith("_") and fn_name not in functions:
                functions.append(fn_name)
                details.append(
                    FunctionDetail(
                        name=fn_name,
                        signature=f"({fn_args.strip()})",
                        is_async="async" in m.group(0),
                    )
                )

        # Class methods in JS/TS
        js_method_matches = re.finditer(
            r"(?:public|private|protected|async|\s)+\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)\s*\{",
            content,
        )
        for m in js_method_matches:
            m_name = m.group(1)
            if (
                m_name
                and m_name not in {"if", "for", "while", "switch", "catch", "function", "constructor"}
                and not m_name.startswith("_")
                and m_name not in functions
            ):
                functions.append(m_name)
                details.append(FunctionDetail(name=m_name, signature=f"({m.group(2).strip()})", is_method=True))

        for cm in re.findall(r"(?:export\s+)?(?:class|interface|type)\s+([a-zA-Z0-9_$]+)", content):
            classes.append(cm)

        # 3. Go functions and struct methods
        go_methods = re.finditer(r"func\s+(?:\(([^)]+)\)\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)", content)
        for gm in go_methods:
            receiver = gm.group(1)
            fn_name = gm.group(2)
            args = gm.group(3)
            if fn_name and fn_name not in {"init", "main"}:
                rec_clean = receiver.split()[-1].lstrip("*") if receiver else ""
                full_name = f"{rec_clean}.{fn_name}" if rec_clean else fn_name
                functions.append(full_name)
                details.append(FunctionDetail(name=full_name, signature=f"({args})", is_method=bool(receiver)))

        # 4. Rust functions and impl methods
        rust_funcs = re.finditer(r"(?:pub\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)", content)
        for rf in rust_funcs:
            fn_name = rf.group(1)
            args = rf.group(2)
            if fn_name:
                functions.append(fn_name)
                details.append(FunctionDetail(name=fn_name, signature=f"({args})", is_async="async" in rf.group(0)))

        for r_struct in re.findall(r"(?:pub\s+)?(?:struct|enum|trait)\s+([a-zA-Z0-9_]+)", content):
            classes.append(r_struct)

        # 5. Java / C# / PHP / Ruby classes and methods
        java_methods = re.finditer(
            r"(?:public|protected|private)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\]]+)\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)",
            content,
        )
        for jm in java_methods:
            fn_name = jm.group(1)
            if fn_name and fn_name not in classes and fn_name not in functions:
                functions.append(fn_name)
                details.append(FunctionDetail(name=fn_name, signature=f"({jm.group(2)})", is_method=True))

        for jc in re.findall(r"(?:public\s+)?class\s+([a-zA-Z0-9_]+)", content):
            if jc not in classes:
                classes.append(jc)

        # PHP methods
        php_methods = re.finditer(r"function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)", content)
        for pm in php_methods:
            p_name = pm.group(1)
            if p_name and not p_name.startswith("__") and p_name not in functions:
                functions.append(p_name)
                details.append(FunctionDetail(name=p_name, signature=f"({pm.group(2)})"))

        # Ruby methods
        rb_methods = re.finditer(r"def\s+([a-zA-Z0-9_!?]+)(?:\s*\(([^)]*)\))?", content)
        for rm in rb_methods:
            r_name = rm.group(1)
            if r_name and r_name not in functions:
                functions.append(r_name)
                details.append(FunctionDetail(name=r_name, signature=f"({rm.group(2) or ''})"))
    except Exception:
        pass

    return functions, details, classes, imports, line_count


def _parse_generic_test(file_path: Path) -> tuple[list[str], list[str]]:
    """Extract test blocks and imports from JS/TS/Go/Rust/Java files."""
    tests: list[str] = []
    imports: list[str] = []

    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")

        # Extract imports
        for imp in re.findall(
            r"""(?:import\s+(?:.*?from\s+)?['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\))""",
            content,
        ):
            imports.append(imp[0] or imp[1])

        # JS / TS it / test blocks
        js_tests = re.findall(r"(?:it|test)\s*\(\s*['\"]([^'\"]+)['\"]", content)
        tests.extend(js_tests)

        # Go test functions
        go_tests = re.findall(r"func\s+(Test[a-zA-Z0-9_]+)\s*\(", content)
        tests.extend(go_tests)

        # Rust #[test] functions
        rust_tests = re.findall(r"#\[test\][\s\n]+fn\s+([a-zA-Z0-9_]+)", content)
        tests.extend(rust_tests)

        # Java / C# @Test annotations
        java_tests = re.findall(
            r"@Test[\s\n]+(?:public\s+)?(?:void\s+)?([a-zA-Z0-9_]+)\s*\(",
            content,
        )
        tests.extend(java_tests)
    except Exception:
        pass
    return tests, imports


def scan_project_structure(
    root_path: Path,
    ecosystem: Ecosystem,
    framework: TestFramework,
    custom_ignored_dirs: list[str] | None = None,
    custom_ignored_files: list[str] | None = None,
) -> tuple[list[SourceModule], list[TestModule]]:
    """
    Scans the repository to identify source modules and test modules with AST metadata.
    """
    root = root_path.resolve()
    source_modules: list[SourceModule] = []
    test_modules: list[TestModule] = []

    effective_ignored_dirs = IGNORED_DIRS.union(set(custom_ignored_dirs or []))
    effective_ignored_files = IGNORED_FILES.union(set(custom_ignored_files or []))

    valid_extensions = {
        ".py",
        ".ts",
        ".js",
        ".jsx",
        ".tsx",
        ".rs",
        ".go",
        ".php",
        ".rb",
        ".cs",
        ".java",
        ".kt",
        ".kts",
        ".scala",
        ".sc",
        ".fs",
        ".vb",
        ".swift",
        ".dart",
        ".ex",
        ".exs",
        ".hs",
        ".lhs",
        ".c",
        ".h",
        ".cpp",
        ".cc",
        ".cxx",
        ".hpp",
        ".hh",
        ".lua",
        ".pl",
        ".pm",
        ".t",
        ".zig",
        ".cr",
        ".clj",
        ".cljs",
        ".cljc",
        ".sh",
        ".bash",
        ".zsh",
        ".bats",
        ".sql",
        ".tf",
        ".tfvars",
        ".hcl",
        ".ps1",
        ".psm1",
        ".psd1",
        ".r",
        ".R",
        ".jl",
        ".groovy",
        ".gradle",
        ".erl",
        ".hrl",
        ".nim",
        ".ml",
        ".mli",
        ".sol",
        ".elm",
        ".d",
        ".v",
    }

    for item in root.rglob("*"):
        if not item.is_file():
            continue

        # Check ignored path components
        rel_parts = set(item.relative_to(root).parts)
        if any(ignored in rel_parts for ignored in effective_ignored_dirs):
            continue

        if item.name in effective_ignored_files or item.suffix not in valid_extensions:
            continue

        rel_path = item.relative_to(root).as_posix()
        is_test = _is_test_file(item, root)

        if is_test:
            if item.suffix == ".py":
                test_funcs, test_imports = _parse_python_test(item)
            else:
                test_funcs, test_imports = _parse_generic_test(item)

            test_modules.append(
                TestModule(
                    rel_path=rel_path,
                    abs_path=str(item),
                    framework=framework,
                    test_functions=test_funcs,
                    imported_modules=test_imports,
                    line_count=len(item.read_text(encoding="utf-8", errors="ignore").splitlines()),
                )
            )
        else:
            if item.suffix == ".py":
                funcs, details, classes, imports, lines = _parse_python_source(item)
            else:
                funcs, details, classes, imports, lines = _parse_generic_source(item)

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
                    function_details=details,
                    classes=classes,
                    imports=imports,
                    is_entrypoint=is_entry,
                    is_utility=is_util,
                    is_model=is_model,
                    is_route=is_route,
                )
            )

    return source_modules, test_modules
