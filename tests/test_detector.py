"""Tests for ecosystem detection and file scanning."""

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


def test_detect_node_vitest(temp_project_dir: Path):
    (temp_project_dir / "package.json").write_text(
        '{"name": "demo-app", "scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "^1.0.0"}}',
        encoding="utf-8",
    )
    eco, fw, cmd, configs = detect_ecosystem(temp_project_dir)
    assert eco == Ecosystem.NODE
    assert fw == TestFramework.VITEST
    assert "vitest" in cmd
    assert "package.json" in configs


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
        "class AuthService:\n"
        "    def login(self, u, p):\n"
        "        pass\n\n"
        "def hash_password(p):\n"
        "    return p\n",
        encoding="utf-8",
    )

    (src_dir / "routes.py").write_text(
        "def get_users():\n    return []\n",
        encoding="utf-8",
    )

    tests_dir = temp_project_dir / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_auth.py").write_text(
        "def test_login():\n    assert True\n\ndef test_hash():\n    assert True\n",
        encoding="utf-8",
    )

    sources, tests = scan_project_structure(temp_project_dir, Ecosystem.PYTHON, TestFramework.PYTEST)

    assert len(sources) == 2
    auth_mod = next(s for s in sources if "auth.py" in s.rel_path)
    assert "AuthService" in auth_mod.classes
    assert "hash_password" in auth_mod.functions
    assert "AuthService.login" in auth_mod.functions

    routes_mod = next(s for s in sources if "routes.py" in s.rel_path)
    assert routes_mod.is_route is True

    assert len(tests) == 1
    assert "test_login" in tests[0].test_functions
    assert "test_hash" in tests[0].test_functions
