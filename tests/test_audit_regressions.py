"""Regression tests for defects found during the full-codebase audit.

Each test here corresponds to a confirmed bug: a wrong answer the tool used to
give, or a file it used to destroy. They are grouped by the module at fault.
"""

import json
from pathlib import Path

from timmytest.coverage import parse_coverage_report
from timmytest.detector.gap_analyzer import _find_matching_test, analyze_test_gaps
from timmytest.detector.models import Ecosystem, SourceModule, TestFramework, TestModule
from timmytest.detector.scanner import _is_test_file, scan_project_structure
from timmytest.integrations.installer import integrate_project
from timmytest.runner.base import split_command


def _src(rel_path: str, **kwargs) -> SourceModule:
    return SourceModule(rel_path=rel_path, abs_path="", language="py", **kwargs)


def _test_mod(rel_path: str, imports=None, functions=None) -> TestModule:
    return TestModule(
        rel_path=rel_path,
        abs_path="",
        framework=TestFramework.PYTEST,
        test_functions=functions if functions is not None else ["test_something"],
        imported_modules=imports or [],
    )


# --------------------------------------------------------------------------- #
# scanner: an ancestor directory must not decide what a test file is
# --------------------------------------------------------------------------- #


def test_a_project_living_under_a_test_directory_still_has_sources(tmp_path):
    """A checkout at .../test/myapp used to classify every file as a test."""
    project = tmp_path / "test" / "myapp"
    (project / "src").mkdir(parents=True)
    (project / "src" / "calculator.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

    sources, tests = scan_project_structure(project, Ecosystem.PYTHON, TestFramework.PYTEST)

    assert [s.rel_path for s in sources] == ["src/calculator.py"]
    assert tests == []


def test_test_directories_inside_the_project_still_count(tmp_path):
    project = tmp_path / "myapp"
    (project / "tests").mkdir(parents=True)
    (project / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")
    (project / "tests" / "helpers.py").write_text("VALUE = 1\n", encoding="utf-8")

    sources, tests = scan_project_structure(project, Ecosystem.PYTHON, TestFramework.PYTEST)

    assert [s.rel_path for s in sources] == ["app.py"]
    assert [t.rel_path for t in tests] == ["tests/helpers.py"]


def test_is_test_file_without_a_root_keeps_its_old_shape():
    assert _is_test_file(Path("project/tests/test_a.py")) is True
    assert _is_test_file(Path("project/src/a.py")) is False


# --------------------------------------------------------------------------- #
# gap analyzer: correlation precision
# --------------------------------------------------------------------------- #


def test_one_import_does_not_cover_every_module_of_that_name():
    """`import myapp.utils` used to mark every utils.py in the repo as tested."""
    tests = [_test_mod("tests/test_api.py", imports=["myapp.utils"])]

    assert _find_matching_test(_src("myapp/utils.py"), tests) is not None
    assert _find_matching_test(_src("services/billing/utils.py"), tests) is None
    assert _find_matching_test(_src("services/auth/utils.py"), tests) is None


def test_a_src_prefix_is_transparent_to_imports():
    tests = [_test_mod("tests/test_auth.py", imports=["auth"])]
    assert _find_matching_test(_src("src/auth.py"), tests) is not None


def test_package_imports_match_their_own_package():
    # The test file is named so that only the import rule can fire — a stem match
    # would answer this question without exercising what is under test.
    tests = [_test_mod("tests/test_suite_alpha.py", imports=["timmytest.registry"])]
    assert _find_matching_test(_src("src/timmytest/registry.py"), tests) is not None
    assert _find_matching_test(_src("other/registry.py"), tests) is None


def test_from_import_of_a_symbol_still_matches_the_module():
    tests = [_test_mod("tests/test_x.py", imports=["myapp.services.billing"])]
    assert _find_matching_test(_src("myapp/services/billing.py"), tests) is not None


def test_a_fixture_file_is_not_a_test_suite():
    """tests/helpers.py used to satisfy the gap for src/helpers.py."""
    fixture = _test_mod("tests/helpers.py", functions=[])
    assert _find_matching_test(_src("src/helpers.py"), [fixture]) is None


def test_a_test_named_file_without_parsed_functions_still_counts():
    """Languages whose test bodies the scanner cannot parse must not regress."""
    unparsed = _test_mod("tests/auth_test.sh", functions=[])
    assert _find_matching_test(_src("src/auth.py"), [unparsed]) is not None


def test_gaps_are_reported_for_uncorrelated_modules():
    sources = [_src("services/billing/utils.py", functions=["charge"])]
    tests = [_test_mod("tests/test_api.py", imports=["myapp.utils"])]

    gaps, score = analyze_test_gaps(sources, tests, Ecosystem.PYTHON, Path("."))

    assert [g.source_module for g in gaps] == ["services/billing/utils.py"]
    assert score == 0.0


# --------------------------------------------------------------------------- #
# coverage: malformed input must not take the run down
# --------------------------------------------------------------------------- #


def test_lcov_da_lines_may_carry_a_checksum(tmp_path):
    """`lcov --checksum` emits DA:<line>,<hits>,<md5> — this used to raise."""
    (tmp_path / "lcov.info").write_text(
        "SF:src/app.js\nDA:1,1,f7a9\nDA:2,0,b31c\nend_of_record\n", encoding="utf-8"
    )
    report = parse_coverage_report(tmp_path)

    assert report is not None
    assert report.total_percent == 50.0
    assert report.files[0].path == "src/app.js"


def test_lcov_total_weights_by_lines_not_by_file(tmp_path):
    body = "\n".join(f"DA:{i},1" for i in range(1, 1001))
    (tmp_path / "lcov.info").write_text(
        f"SF:src/big.js\n{body}\nend_of_record\nSF:src/tiny.js\nDA:1,0\nend_of_record\n",
        encoding="utf-8",
    )
    report = parse_coverage_report(tmp_path)

    # 1000 of 1001 lines are covered. Averaging the two files would say 50%.
    assert report.total_percent == 99.9


def test_a_malformed_coverage_json_is_ignored(tmp_path):
    (tmp_path / "coverage.json").write_text('{"totals": {"percent_cov', encoding="utf-8")
    assert parse_coverage_report(tmp_path) is None


def test_a_missing_explicit_coverage_file_is_ignored(tmp_path):
    assert parse_coverage_report(tmp_path, tmp_path / "nope.json") is None


def test_an_xml_report_declaring_entities_is_refused(tmp_path):
    """Entity expansion turns a small file into gigabytes; do not parse it."""
    (tmp_path / "coverage.xml").write_text(
        '<?xml version="1.0"?>\n'
        "<!DOCTYPE coverage [\n"
        '  <!ENTITY a "AAAAAAAAAA">\n'
        '  <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">\n'
        "]>\n"
        '<coverage line-rate="0.5"><class filename="&b;" line-rate="0.1"/></coverage>\n',
        encoding="utf-8",
    )
    assert parse_coverage_report(tmp_path) is None


def test_a_normal_cobertura_report_still_parses(tmp_path):
    (tmp_path / "coverage.xml").write_text(
        '<?xml version="1.0"?>\n<coverage line-rate="0.75">'
        '<class filename="src/a.py" line-rate="0.5"/></coverage>\n',
        encoding="utf-8",
    )
    report = parse_coverage_report(tmp_path)

    assert report is not None
    assert report.total_percent == 75.0


# --------------------------------------------------------------------------- #
# installer: --force must not destroy user-owned files
# --------------------------------------------------------------------------- #


def test_force_never_regenerates_the_user_config(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    tuned = "ignored_dirs: [legacy]\ncustom_test_cmd: pytest -x\n"
    (tmp_path / ".timmytest.yml").write_text(tuned, encoding="utf-8")

    integrate_project(tmp_path, force=True)

    assert (tmp_path / ".timmytest.yml").read_text(encoding="utf-8") == tuned


def test_force_keeps_every_other_mcp_server(tmp_path):
    """.cursor/mcp.json is shared; overwriting it unregistered the user's servers."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    (cursor / "mcp.json").write_text(
        json.dumps({"mcpServers": {"postgres": {"command": "pg-mcp"}}}), encoding="utf-8"
    )

    integrate_project(tmp_path, force=True)
    servers = json.loads((cursor / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]

    assert sorted(servers) == ["postgres", "timmytest"]
    assert servers["postgres"] == {"command": "pg-mcp"}


def test_an_unparseable_mcp_config_is_left_alone(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    cursor = tmp_path / ".cursor"
    cursor.mkdir()
    (cursor / "mcp.json").write_text("{ not json", encoding="utf-8")

    integrate_project(tmp_path, force=True)

    assert (cursor / "mcp.json").read_text(encoding="utf-8") == "{ not json"


def test_mcp_config_is_created_when_absent(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")

    integrate_project(tmp_path)
    servers = json.loads((tmp_path / ".cursor" / "mcp.json").read_text(encoding="utf-8"))["mcpServers"]

    assert list(servers) == ["timmytest"]


# --------------------------------------------------------------------------- #
# runner: Windows command splitting
# --------------------------------------------------------------------------- #


def test_windows_paths_survive_command_splitting():
    """posix=True splitting ate the backslashes: C:\\tools\\pytest.exe -> C:toolspytest.exe."""
    import os

    argv = split_command(r"C:\tools\py\pytest.exe -ra tests\unit")
    if os.name == "nt":
        assert argv == [r"C:\tools\py\pytest.exe", "-ra", r"tests\unit"]
    else:
        assert argv[1] == "-ra"


def test_quoted_arguments_stay_together():
    argv = split_command('pytest -k "auth and not slow"')
    assert argv[:2] == ["pytest", "-k"]
    assert argv[2] == "auth and not slow"


def test_unbalanced_quotes_do_not_raise():
    assert split_command('pytest -k "unclosed') == ["pytest", "-k", '"unclosed']


# --------------------------------------------------------------------------- #
# orchestrator: incremental selection must reach every ecosystem
# --------------------------------------------------------------------------- #


def test_incremental_paths_reach_the_generic_runner(monkeypatch, tmp_path):
    """--changed used to be silently dropped for Java/.NET/PHP/Ruby."""
    from timmytest.runner import generic_runner, orchestrator

    seen = {}

    def fake_exec(cmd, cwd, timeout_seconds=60, env=None):
        seen["cmd"] = cmd
        return 0, "", False

    monkeypatch.setattr(generic_runner, "execute_safe_subprocess", fake_exec)

    orchestrator.run_project_tests(
        root_dir=tmp_path,
        ecosystem=Ecosystem.RUBY,
        framework=TestFramework.RSPEC,
        test_paths=["spec/user_spec.rb"],
    )

    assert "spec/user_spec.rb" in seen["cmd"]


# --------------------------------------------------------------------------- #
# analysis: empty --changed selection means "run nothing", not "run everything"
# --------------------------------------------------------------------------- #


def test_empty_changed_selection_skips_execution(monkeypatch, tmp_path):
    """A clean tree under `--changed` used to fall back to running the WHOLE
    suite - the exact cost the flag exists to avoid."""
    from timmytest import analysis

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_app.py").write_text(
        "def test_run():\n    assert run() == 1\n", encoding="utf-8"
    )

    ran = {"executed": False}

    def fake_run_tests(**kwargs):
        ran["executed"] = True

    monkeypatch.setattr(analysis, "get_affected_test_paths", lambda *a, **k: [], raising=False)
    monkeypatch.setattr("timmytest.git_changed.get_affected_test_paths", lambda *a, **k: [])
    monkeypatch.setattr(
        "timmytest.runner.orchestrator.run_project_tests",
        lambda **kwargs: fake_run_tests(**kwargs),
    )

    audit = analysis.analyze_project(project_dir=tmp_path, execute_tests=True, changed=True)
    assert audit.test_run.has_executed is False
    assert ran["executed"] is False


def test_iter_project_files_matches_uppercase_extensions(tmp_path):
    """`CALC.PY` is source code just like `calc.py`; the case-sensitive suffix
    check used to drop uppercase files from the scan entirely."""
    from timmytest.detector.scanner import iter_project_files

    (tmp_path / "UTIL.PY").write_text("X = 1\n", encoding="utf-8")
    (tmp_path / "lower.py").write_text("Y = 2\n", encoding="utf-8")

    names = {p.name for p in iter_project_files(tmp_path, set(), set(), {".py"})}
    assert names == {"UTIL.PY", "lower.py"}
