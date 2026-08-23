"""AST and regex-based source and test file scanner with multi-language AST extraction."""

import ast
import re
from collections.abc import Iterator
from pathlib import Path

from timmytest import walk
from timmytest.detector.models import (
    Ecosystem,
    FunctionDetail,
    SourceModule,
    TestFramework,
    TestModule,
)

#: Re-exported for callers that have always imported it from here.
IGNORED_DIRS = walk.IGNORED_DIRS

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

# Tooling config is not application code. Listing it by exact filename only ever
# covered a handful of spellings, so `next.config.js`, `playwright.config.ts` and
# `vitest.setup.js` were reported as HIGH-priority untested modules - advice no
# one can act on, and it inflates the gap count.
_CONFIG_EXTENSIONS = {"js", "cjs", "mjs", "jsx", "ts", "cts", "mts", "tsx"}
_CONFIG_STEMS = {"babel", "gulpfile", "gruntfile", "webpack", "rollup", "commitlint", "lint-staged"}


def _is_tooling_config(name: str) -> bool:
    """True for build/tool configuration files such as ``next.config.js``."""
    stem, dot, extension = name.lower().rpartition(".")
    if not dot or extension not in _CONFIG_EXTENSIONS:
        return False
    return stem.endswith(".config") or stem.endswith(".setup") or stem in _CONFIG_STEMS


TEST_DIR_NAMES = {"tests", "test", "__tests__", "spec", "specs"}

#: Files above this size are bundles, vendored blobs or generated artefacts, not
#: code anyone writes tests for. Running the regex parsers over a 4 MB minified
#: bundle costs seconds and yields nonsense identifiers.
MAX_SOURCE_BYTES = 1_500_000

#: Generated/minified artefacts keep a normal extension, so the size guard alone
#: does not catch the small ones.
_GENERATED_MARKERS = (".min.js", ".min.ts", ".min.css", ".bundle.js", "-lock.js", ".d.ts")


def _read_source(path: Path) -> str:
    """Read a file for parsing, or return '' when it is not worth parsing."""
    try:
        if path.stat().st_size > MAX_SOURCE_BYTES:
            return ""
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def iter_project_files(
    root: Path,
    ignored_dirs: set[str],
    ignored_files: set[str],
    valid_extensions: set[str],
) -> Iterator[Path]:
    """Yield candidate source/test files, pruning ignored directories as it walks.

    ``rglob`` descends into every directory and filters afterwards, so a repo
    with ``node_modules`` paid for a full traversal of tens of thousands of files
    it then threw away - the dominant cost of a scan. ``os.walk`` lets the
    ignored directories be pruned before they are entered.
    """
    for dirpath, filenames in walk.walk_dirs(root, ignored_dirs):
        current = Path(dirpath)
        for filename in filenames:
            if filename in ignored_files or _is_tooling_config(filename):
                continue
            lowered = filename.lower()
            if lowered.endswith(_GENERATED_MARKERS):
                continue
            # Match extensions case-insensitively: `CALC.PY` or `Util.C` is
            # source code just as much as its lowercase twin, and an
            # uppercase-sensitive comparison silently dropped those files -
            # they then showed up neither as modules nor as test gaps.
            suffix = lowered[lowered.rfind(".") :] if "." in filename else ""
            if suffix not in valid_extensions:
                continue
            yield current / filename


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


# --------------------------------------------------------------------------- #
# Source extraction patterns
#
# Compiled once at import: the scanner applies them to every file in a repo, and
# `re`'s internal cache is capped and shared with every other caller.
# --------------------------------------------------------------------------- #

_IMPORT_RE = re.compile(
    r"""(?:import\s+(?:.*?from\s+)?['"]([^'"]+)['"]|require\(['"]([^'"]+)['"]\)|use\s+([a-zA-Z0-9_:\\]+);)"""
)
_JS_FUNC_RE = re.compile(
    r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_$]+)\s*\(([^)]*)\)"
    r"|(?:export\s+)?(?:const|let|var)\s+([a-zA-Z0-9_$]+)\s*=\s*(?:async\s*)?"
    r"(?:\(([^)]*)\)|[a-zA-Z0-9_$]+)(?:\s*:\s*[^=]+)?\s*=>"
)
#: Method declarations. The previous form - `(?:public|private|protected|async|\s)+\s+`
#: - nests two quantifiers that both match whitespace, so a non-matching line
#: forced exponential backtracking (a single 60 KB React page cost 0.4s, and a
#: pathological file could hang the scan outright). Anchoring to the start of a
#: line is both linear and more accurate: real method declarations start one.
_METHOD_RE = re.compile(
    r"^[ \t]*(?:(?:public|private|protected|static|async|override|final)\s+)*"
    r"([a-zA-Z0-9_$]+)\s*\(([^)\n]*)\)\s*\{",
    re.MULTILINE,
)
_NOT_METHOD_NAMES = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "function",
    "constructor",
    "return",
    "do",
    "else",
    "try",
    "with",
}
_JS_TYPE_RE = re.compile(r"(?:export\s+)?(?:class|interface|type)\s+([a-zA-Z0-9_$]+)")
_GO_FUNC_RE = re.compile(r"func\s+(?:\(([^)]+)\)\s+)?([a-zA-Z0-9_]+)\s*\(([^)]*)\)")
_RUST_FUNC_RE = re.compile(r"(?:pub\s+)?(?:async\s+)?fn\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)")
_RUST_TYPE_RE = re.compile(r"(?:pub\s+)?(?:struct|enum|trait)\s+([a-zA-Z0-9_]+)")
_JAVA_METHOD_RE = re.compile(
    r"(?:public|protected|private)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\]]+)\s+"
    r"([a-zA-Z0-9_]+)\s*\(([^)]*)\)"
)
_JAVA_CLASS_RE = re.compile(r"(?:public\s+)?class\s+([a-zA-Z0-9_]+)")
_PHP_FUNC_RE = re.compile(r"function\s+([a-zA-Z0-9_]+)\s*\(([^)]*)\)")
_RUBY_DEF_RE = re.compile(r"def\s+([a-zA-Z0-9_!?]+)(?:\s*\(([^)]*)\))?")

_JS_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
_GO_EXTENSIONS = {".go"}
_RUST_EXTENSIONS = {".rs"}
_JVM_EXTENSIONS = {".java", ".cs", ".kt", ".kts", ".scala", ".sc", ".groovy", ".gradle", ".vb", ".fs"}
_PHP_EXTENSIONS = {".php"}
_RUBY_EXTENSIONS = {".rb"}


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
        content = _read_source(file_path)
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


def _parse_python_test(file_path: Path) -> tuple[list[str], list[str], int]:
    """Extract test functions, imported modules and line count from a Python test file."""
    test_funcs: list[str] = []
    imports: list[str] = []
    line_count = 0

    try:
        content = _read_source(file_path)
        line_count = len(content.splitlines())
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
    return test_funcs, imports, line_count


def _extract_types(content: str, classes: list[str], patterns: tuple[re.Pattern[str], ...]) -> None:
    """Collect type declarations, running only the patterns the language needs."""
    for pattern in patterns:
        for name in pattern.findall(content):
            if name not in classes:
                classes.append(name)


def _extract_js(content: str, functions: list[str], details: list[FunctionDetail]) -> None:
    for m in _JS_FUNC_RE.finditer(content):
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

    for m in _METHOD_RE.finditer(content):
        m_name = m.group(1)
        if (
            m_name
            and m_name not in _NOT_METHOD_NAMES
            and not m_name.startswith("_")
            and m_name not in functions
        ):
            functions.append(m_name)
            details.append(FunctionDetail(name=m_name, signature=f"({m.group(2).strip()})", is_method=True))


def _extract_go(content: str, functions: list[str], details: list[FunctionDetail]) -> None:
    for gm in _GO_FUNC_RE.finditer(content):
        receiver, fn_name, args = gm.group(1), gm.group(2), gm.group(3)
        if fn_name and fn_name not in {"init", "main"}:
            rec_clean = receiver.split()[-1].lstrip("*") if receiver else ""
            full_name = f"{rec_clean}.{fn_name}" if rec_clean else fn_name
            functions.append(full_name)
            details.append(FunctionDetail(name=full_name, signature=f"({args})", is_method=bool(receiver)))


def _extract_rust(content: str, functions: list[str], details: list[FunctionDetail]) -> None:
    for rf in _RUST_FUNC_RE.finditer(content):
        fn_name = rf.group(1)
        if fn_name:
            functions.append(fn_name)
            details.append(
                FunctionDetail(name=fn_name, signature=f"({rf.group(2)})", is_async="async" in rf.group(0))
            )


def _extract_jvm(
    content: str, functions: list[str], details: list[FunctionDetail], classes: list[str]
) -> None:
    for jm in _JAVA_METHOD_RE.finditer(content):
        fn_name = jm.group(1)
        if fn_name and fn_name not in classes and fn_name not in functions:
            functions.append(fn_name)
            details.append(FunctionDetail(name=fn_name, signature=f"({jm.group(2)})", is_method=True))


def _extract_php(content: str, functions: list[str], details: list[FunctionDetail]) -> None:
    for pm in _PHP_FUNC_RE.finditer(content):
        p_name = pm.group(1)
        if p_name and not p_name.startswith("__") and p_name not in functions:
            functions.append(p_name)
            details.append(FunctionDetail(name=p_name, signature=f"({pm.group(2)})"))


def _extract_ruby(content: str, functions: list[str], details: list[FunctionDetail]) -> None:
    for rm in _RUBY_DEF_RE.finditer(content):
        r_name = rm.group(1)
        if r_name and r_name not in functions:
            functions.append(r_name)
            details.append(FunctionDetail(name=r_name, signature=f"({rm.group(2) or ''})"))


def _parse_generic_source(
    file_path: Path,
) -> tuple[list[str], list[FunctionDetail], list[str], list[str], int]:
    """Parse a non-Python source file into functions, classes, imports and size.

    Extraction is dispatched on the file's extension. Running every language's
    patterns over every file was both slow and wrong: PHP's ``function name()``
    and Java's method pattern happily match TypeScript, so a ``.ts`` file picked
    up phantom "methods" from three other languages' rules. Extensions with no
    dedicated grammar still get the broad pass, which is how C/C++/Swift and
    friends were being handled all along.
    """
    functions: list[str] = []
    details: list[FunctionDetail] = []
    classes: list[str] = []
    imports: list[str] = []
    line_count = 0

    try:
        content = _read_source(file_path)
        line_count = len(content.splitlines())
        suffix = file_path.suffix.lower()

        for m in _IMPORT_RE.finditer(content):
            imp = m.group(1) or m.group(2) or m.group(3)
            if imp:
                imports.append(imp)

        if suffix in _JS_EXTENSIONS:
            _extract_types(content, classes, (_JS_TYPE_RE,))
            _extract_js(content, functions, details)
        elif suffix in _GO_EXTENSIONS:
            # Go declares types as `type Foo struct`, which the JS type pattern
            # already covers.
            _extract_types(content, classes, (_JS_TYPE_RE,))
            _extract_go(content, functions, details)
        elif suffix in _RUST_EXTENSIONS:
            _extract_types(content, classes, (_RUST_TYPE_RE,))
            _extract_rust(content, functions, details)
        elif suffix in _JVM_EXTENSIONS:
            _extract_types(content, classes, (_JS_TYPE_RE, _JAVA_CLASS_RE))
            _extract_jvm(content, functions, details, classes)
        elif suffix in _PHP_EXTENSIONS:
            _extract_types(content, classes, (_JAVA_CLASS_RE,))
            _extract_php(content, functions, details)
        elif suffix in _RUBY_EXTENSIONS:
            _extract_types(content, classes, (_JAVA_CLASS_RE,))
            _extract_ruby(content, functions, details)
        else:
            _extract_types(content, classes, (_JS_TYPE_RE, _RUST_TYPE_RE, _JAVA_CLASS_RE))
            _extract_js(content, functions, details)
            _extract_go(content, functions, details)
            _extract_rust(content, functions, details)
            _extract_jvm(content, functions, details, classes)
            _extract_php(content, functions, details)
            _extract_ruby(content, functions, details)
    except Exception:
        pass

    return functions, details, classes, imports, line_count


def _parse_generic_test(file_path: Path) -> tuple[list[str], list[str], int]:
    """Extract test blocks, imports and line count from JS/TS/Go/Rust/Java files."""
    tests: list[str] = []
    imports: list[str] = []
    line_count = 0

    try:
        content = _read_source(file_path)
        line_count = len(content.splitlines())

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
    return tests, imports, line_count


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

    for item in iter_project_files(root, effective_ignored_dirs, effective_ignored_files, valid_extensions):
        rel_path = item.relative_to(root).as_posix()
        is_test = _is_test_file(item, root)

        if is_test:
            if item.suffix == ".py":
                test_funcs, test_imports, test_lines = _parse_python_test(item)
            else:
                test_funcs, test_imports, test_lines = _parse_generic_test(item)

            test_modules.append(
                TestModule(
                    rel_path=rel_path,
                    abs_path=str(item),
                    framework=framework,
                    test_functions=test_funcs,
                    imported_modules=test_imports,
                    line_count=test_lines,
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
