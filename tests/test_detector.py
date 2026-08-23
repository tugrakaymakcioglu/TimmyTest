"""Tests for ecosystem detection and file scanning with rich AST extraction."""

from pathlib import Path

from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.models import Ecosystem, TestFramework
from timmytest.detector.scanner import scan_project_structure


def test_detect_python_pytest(temp_project_dir: Path):
    (temp_project_dir / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n[tool.pytest.ini_options]\n',
        encoding="utf-8",
    )
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.PYTHON
    assert fw == TestFramework.PYTEST
    assert "pytest" in cmd
    assert "pyproject.toml" in configs


def test_detect_python_uv(temp_project_dir: Path):
    (temp_project_dir / "pyproject.toml").write_text('[project]\nname = "demo"\n', encoding="utf-8")
    (temp_project_dir / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.PYTHON
    assert "uv run pytest" in cmd


def test_detect_node_pnpm_vitest(temp_project_dir: Path):
    (temp_project_dir / "package.json").write_text(
        '{"name": "demo-app", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "^1.0.0"}}',
        encoding="utf-8",
    )
    (temp_project_dir / "pnpm-lock.yaml").write_text("lockfileVersion: 5.4\n", encoding="utf-8")
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.NODE
    assert fw == TestFramework.VITEST
    assert "pnpm vitest run" in cmd
    assert "pnpm-lock.yaml" in configs


def test_detect_rust_cargo(temp_project_dir: Path):
    (temp_project_dir / "Cargo.toml").write_text(
        '[package]\nname = "demo"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.RUST
    assert fw == TestFramework.CARGO
    assert cmd == "cargo test"


def test_detect_go(temp_project_dir: Path):
    (temp_project_dir / "go.mod").write_text(
        "module example.com/demo\n\ngo 1.22\n",
        encoding="utf-8",
    )
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.GO
    assert fw == TestFramework.GO_TEST
    assert "go test" in cmd


def test_scan_project_structure_python(temp_project_dir: Path):
    src_dir = temp_project_dir / "src" / "demo"
    src_dir.mkdir(parents=True)

    (src_dir / "auth.py").write_text(
        "import os\nfrom pathlib import Path\n\n"
        "class AuthService:\n"
        '    """Service managing authentication."""\n'
        "    def login(self, username: str, password: str) -> bool:\n"
        '        """Authenticate user credentials."""\n'
        "        return True\n\n"
        "async def hash_password(plain: str) -> str:\n"
        '    """Compute password hash."""\n'
        "    return plain\n",
        encoding="utf-8",
    )

    (src_dir / "routes.py").write_text(
        "def get_users():\n    return []\n",
        encoding="utf-8",
    )

    tests_dir = temp_project_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "from demo.auth import AuthService\n\ndef test_login():\n    assert True\n",
        encoding="utf-8",
    )

    sources, tests = scan_project_structure(temp_project_dir, Ecosystem.PYTHON, TestFramework.PYTEST)

    assert len(sources) == 2
    auth_mod = next(s for s in sources if "auth.py" in s.rel_path)
    assert "AuthService" in auth_mod.classes
    assert "hash_password" in auth_mod.functions
    assert "AuthService.login" in auth_mod.functions
    assert "os" in auth_mod.imports

    # Check FunctionDetail signatures and docstrings
    hash_fn = next(fd for fd in auth_mod.function_details if fd.name == "hash_password")
    assert hash_fn.is_async is True
    assert "(plain: str) -> str" in hash_fn.signature
    assert "Compute password hash." in hash_fn.docstring

    login_fn = next(fd for fd in auth_mod.function_details if fd.name == "AuthService.login")
    assert login_fn.is_method is True
    assert "username: str" in login_fn.signature
    assert "Authenticate user credentials." in login_fn.docstring

    routes_mod = next(s for s in sources if "routes.py" in s.rel_path)
    assert routes_mod.is_route is True

    assert len(tests) == 1
    assert "test_login" in tests[0].test_functions
    assert "demo.auth" in tests[0].imported_modules


def test_scan_skips_tooling_config_files(temp_project_dir: Path):
    """Build config is not application code and must not become a test gap."""
    for name in (
        "next.config.js",
        "playwright.config.ts",
        "vitest.config.js",
        "vitest.setup.js",
        "eslint.config.mjs",
        "babel.js",
    ):
        (temp_project_dir / name).write_text("export default {};\n", encoding="utf-8")
    (temp_project_dir / "middleware.js").write_text(
        "export function middleware(req) { return req; }\n", encoding="utf-8"
    )

    sources, _ = scan_project_structure(temp_project_dir, Ecosystem.NODE, TestFramework.VITEST)

    assert [s.rel_path for s in sources] == ["middleware.js"]


def test_scan_skips_generated_and_oversized_files(temp_project_dir: Path):
    """Minified bundles and giant generated blobs are not testable source."""
    (temp_project_dir / "app.min.js").write_text("export function a(){}", encoding="utf-8")
    (temp_project_dir / "types.d.ts").write_text("export declare function b(): void;", encoding="utf-8")
    (temp_project_dir / "huge.js").write_text("// " + "x" * 1_600_000, encoding="utf-8")
    (temp_project_dir / "real.js").write_text("export function c(){}\n", encoding="utf-8")

    sources, _ = scan_project_structure(temp_project_dir, Ecosystem.NODE, TestFramework.VITEST)
    by_path = {s.rel_path: s for s in sources}

    assert "real.js" in by_path
    assert "app.min.js" not in by_path
    assert "types.d.ts" not in by_path
    # The oversized file is still listed as a module, but is not parsed.
    assert by_path["huge.js"].functions == []


def test_scan_does_not_apply_other_languages_patterns(temp_project_dir: Path):
    """A TS file must not collect phantom methods from the PHP/Ruby/Java rules."""
    (temp_project_dir / "svc.ts").write_text(
        "export class Svc {\n  run(input: string) { return input; }\n}\ndef notRuby = 1\n",
        encoding="utf-8",
    )
    sources, _ = scan_project_structure(temp_project_dir, Ecosystem.NODE, TestFramework.VITEST)
    module = next(s for s in sources if s.rel_path == "svc.ts")

    assert "Svc" in module.classes
    assert "run" in module.functions
    assert "notRuby" not in module.functions


def test_scan_project_structure_multi_lang(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir(parents=True)

    # JS/TS file
    (src_dir / "service.ts").write_text(
        "export const fetchUser = async (id: string): Promise<User> => { return {}; };\n"
        "export class UserService {\n  public async deleteUser(id: string) {}\n}\n",
        encoding="utf-8",
    )

    # Go file
    (src_dir / "handler.go").write_text(
        "package main\n\ntype Server struct{}\n\nfunc (s *Server) HandleRequest(w ResponseWriter, r *Request) {}\n",
        encoding="utf-8",
    )

    # Java file
    (src_dir / "App.java").write_text(
        "public class App {\n    public static void processOrder(int orderId) {}\n}\n",
        encoding="utf-8",
    )

    sources, _ = scan_project_structure(temp_project_dir, Ecosystem.NODE, TestFramework.VITEST)

    ts_mod = next(s for s in sources if "service.ts" in s.rel_path)
    assert "fetchUser" in ts_mod.functions
    assert "deleteUser" in ts_mod.functions
    assert "UserService" in ts_mod.classes

    go_mod = next(s for s in sources if "handler.go" in s.rel_path)
    assert "Server.HandleRequest" in go_mod.functions

    java_mod = next(s for s in sources if "App.java" in s.rel_path)
    assert "App" in java_mod.classes
    assert "processOrder" in java_mod.functions
