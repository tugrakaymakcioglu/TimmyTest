"""Tests for coverage report parsing (coverage.py JSON, Cobertura XML, LCOV)."""

import json
from pathlib import Path

from timmytest.coverage import discover_coverage_file, find_low_coverage_files, parse_coverage_report
from timmytest.detector.models import CoverageReport

COVERAGE_JSON = {
    "meta": {"version": "7.6.0", "format": 3},
    "files": {
        "src/foo.py": {
            "executed_lines": [1, 2, 3],
            "summary": {"percent_covered": 90.0, "num_statements": 10},
        },
        "src/bar.py": {
            "executed_lines": [1],
            "summary": {"percent_covered": 20.0, "num_statements": 20},
        },
    },
    "totals": {"percent_covered": 55.0, "num_statements": 30},
}

COBERTURA_XML = """<?xml version="1.0" ?>
<coverage line-rate="0.55" lines-covered="11" lines-valid="20" version="gcovr">
  <sources><source>/project</source></sources>
  <packages>
    <package name="." line-rate="0.55">
      <classes>
        <class name="foo" filename="src/foo.py" line-rate="0.9"/>
        <class name="bar" filename="src/bar.py" line-rate="0.2"/>
      </classes>
    </package>
  </packages>
</coverage>
"""

LCOV_INFO = """TN:
SF:/project/src/foo.py
DA:1,1
DA:2,1
DA:3,0
LF:3
LH:2
end_of_record
SF:/project/src/bar.py
DA:1,1
LF:1
LH:1
end_of_record
"""


def test_parse_coverage_json():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "coverage.json"
        p.write_text(json.dumps(COVERAGE_JSON), encoding="utf-8")
        report = parse_coverage_report(Path(d), explicit=p)
        assert isinstance(report, CoverageReport)
        assert report.source == "coverage.json"
        assert report.total_percent == 55.0
        assert len(report.files) == 2
        assert report.files[0].percent == 20.0  # sorted ascending


def test_parse_cobertura():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "coverage.xml"
        p.write_text(COBERTURA_XML, encoding="utf-8")
        report = parse_coverage_report(Path(d), explicit=p)
        assert report.source == "cobertura.xml"
        assert report.total_percent == 55.0
        assert {f.path for f in report.files} == {"src/foo.py", "src/bar.py"}


def test_parse_lcov():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "lcov.info"
        p.write_text(LCOV_INFO, encoding="utf-8")
        report = parse_coverage_report(Path(d), explicit=p)
        assert report.source == "lcov.info"
        # foo.py: 2/3 lines hit, bar.py: 1/1 -> 3 hit of 4 found = 75%.
        # Averaging the per-file percentages instead would say 83.35%, which
        # over-reports whenever the small files are the well-covered ones.
        assert report.total_percent == 75.0
        assert [f.percent for f in report.files] == [66.7, 100.0]


def test_discover_coverage_file_autodetect():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "cobertura.xml").write_text(COBERTURA_XML, encoding="utf-8")
        found = discover_coverage_file(root)
        assert found is not None
        assert found.name == "cobertura.xml"


def test_discover_none_when_missing():
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        assert discover_coverage_file(Path(d)) is None


def test_find_low_coverage_files():
    report = CoverageReport(
        source="coverage.json",
        total_percent=55.0,
        files=[
            {"path": "a.py", "percent": 20.0},
            {"path": "b.py", "percent": 90.0},
            {"path": "c.py", "percent": 55.0},
        ],
    )
    low = find_low_coverage_files(report, threshold=60.0)
    assert [f.path for f in low] == ["a.py", "c.py"]
