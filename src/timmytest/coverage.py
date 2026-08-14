"""Coverage report parsing for coverage-aware gap analysis.

Supports three widely-used machine-readable coverage formats:

* ``coverage.json``  — coverage.py JSON report (``coverage json``)
* ``cobertura.xml``  — Cobertura XML (also emitted by ``coverage xml`` and many
  Node/Rust/Go coverage exporters)
* ``lcov.info``      — LCOV tracefile (Istanbul/nyc, llvm-cov, genhtml)
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from timmytest.detector.models import CoverageReport, FileCoverage

# Default discovery order for auto-detecting a coverage report in a project root.
_DISCOVERY_NAMES = ("coverage.json", "coverage.xml", "cobertura.xml", "lcov.info")


#: Entity declarations turn a few hundred bytes of XML into gigabytes of expanded
#: text ("billion laughs"). ElementTree expands them happily, and a coverage
#: report is exactly the kind of file that arrives from somewhere else.
_XML_ENTITY_MARKERS = ("<!entity", "<!doctype")


def discover_coverage_file(root: Path, explicit: Path | None = None) -> Path | None:
    """Return the coverage report path to parse, or None if unavailable."""
    if explicit is not None:
        resolved = explicit.resolve()
        return resolved if resolved.is_file() else None
    for name in _DISCOVERY_NAMES:
        candidate = root / name
        if candidate.is_file():
            return candidate
    return None


def parse_coverage_report(root: Path, explicit: Path | None = None) -> CoverageReport | None:
    """Parse a project's coverage report, auto-discovering the format.

    Returns ``None`` for anything unreadable or malformed. A coverage report is
    an *optional* input to the audit: a stale or half-written one should cost the
    user their coverage panel, never their whole run.
    """
    path = discover_coverage_file(root, explicit)
    if path is None:
        return None

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    lowered = raw.lstrip().lower()

    try:
        if lowered.startswith("<?xml") or lowered.startswith("<coverage"):
            if any(marker in lowered for marker in _XML_ENTITY_MARKERS):
                return None
            return _parse_cobertura(raw)
        if path.suffix == ".json":
            return _parse_coverage_json(raw)
        if path.suffix == ".info" or "end_of_record" in raw:
            return _parse_lcov(raw)

        # Last-resort format sniff by content.
        if raw.lstrip().startswith("{"):
            return _parse_coverage_json(raw)
    except (ValueError, TypeError, AttributeError, KeyError, ET.ParseError):
        return None
    return None


def _parse_coverage_json(raw: str) -> CoverageReport:
    """Parse coverage.py's ``coverage json`` output format."""
    data = json.loads(raw)
    totals = data.get("totals", {})
    total_percent = round(float(totals.get("percent_covered", 0.0)), 1)

    files: list[FileCoverage] = []
    for path, meta in data.get("files", {}).items():
        percent = round(float(meta.get("summary", {}).get("percent_covered", 0.0)), 1)
        files.append(FileCoverage(path=path, percent=percent))
    files.sort(key=lambda f: f.percent)
    return CoverageReport(source="coverage.json", total_percent=total_percent, files=files)


def _parse_cobertura(raw: str) -> CoverageReport:
    """Parse Cobertura XML (``coverage xml`` or exporters like nyc/cargo-llvm-cov)."""
    root_el = ET.fromstring(raw)
    line_rate = float(root_el.attrib.get("line-rate", "0.0"))
    total_percent = round(line_rate * 100.0, 1)

    files: list[FileCoverage] = []
    for cls in root_el.iter("class"):
        filename = cls.attrib.get("filename")
        if not filename:
            continue
        cls_rate = float(cls.attrib.get("line-rate", "0.0"))
        files.append(FileCoverage(path=filename, percent=round(cls_rate * 100.0, 1)))
    files.sort(key=lambda f: f.percent)
    return CoverageReport(source="cobertura.xml", total_percent=total_percent, files=files)


def _parse_lcov(raw: str) -> CoverageReport:
    """Parse an LCOV tracefile (``SF``/``DA`` records).

    ``DA`` is ``DA:<line>,<hits>[,<checksum>]`` — the checksum field is optional
    but standard (``lcov --checksum``, genhtml), so the hit count is taken as the
    *second* field rather than everything after the first comma.

    The overall figure is total-lines-hit over total-lines-found, not the mean of
    the per-file percentages: averaging lets a one-line file at 0% cancel out a
    thousand-line file at 100%.
    """
    files: list[FileCoverage] = []
    current_path: str | None = None
    lines_found = 0
    lines_hit = 0
    all_found = 0
    all_hit = 0

    for line in raw.splitlines():
        if line.startswith("SF:"):
            current_path = line[3:].strip()
            lines_found = 0
            lines_hit = 0
        elif line.startswith("DA:"):
            fields = line[3:].split(",")
            if len(fields) < 2:
                continue
            try:
                hits = int(fields[1].strip())
            except ValueError:
                continue
            lines_found += 1
            if hits > 0:
                lines_hit += 1
        elif line.strip() == "end_of_record":
            if current_path is not None and lines_found > 0:
                percent = round((lines_hit / lines_found) * 100.0, 1)
                files.append(FileCoverage(path=current_path, percent=percent))
                all_found += lines_found
                all_hit += lines_hit
            current_path = None

    # A tracefile whose final record is not terminated still carries evidence.
    if current_path is not None and lines_found > 0:
        files.append(FileCoverage(path=current_path, percent=round((lines_hit / lines_found) * 100.0, 1)))
        all_found += lines_found
        all_hit += lines_hit

    files.sort(key=lambda f: f.percent)
    total = round((all_hit / all_found) * 100.0, 1) if all_found else 0.0
    return CoverageReport(source="lcov.info", total_percent=total, files=files)


def find_low_coverage_files(report: CoverageReport, threshold: float = 60.0) -> list[FileCoverage]:
    """Return files whose coverage is below ``threshold`` percent, worst first."""
    return [f for f in report.files if f.percent < threshold]
