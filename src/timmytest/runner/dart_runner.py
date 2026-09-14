"""Parser for `dart test` / `flutter test` console output.

Both runners share one reporter family: a live counter (``00:02 +3 -1:``),
per-test ``[E]`` error markers, and a final verdict of ``All tests passed!``
or ``Some tests failed.``. Flutter keeps the same shapes.

The counters are *cumulative snapshots*, not deltas: every progress line
restates the totals so far, so the last counter seen on each line wins and
tokens must never be summed across lines.
"""

import re

from timmytest.detector.models import FailureDetail

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

_ALL_PASSED_RE = re.compile(r"\bAll tests passed", re.IGNORECASE)
_SOME_FAILED_RE = re.compile(r"\bSome tests failed", re.IGNORECASE)
_TOTAL_IN_VERDICT = re.compile(r"\(total[:\s]+(\d+)\)", re.IGNORECASE)

# One cumulative counter token inside a progress line:
#   +3      three passes so far
#   -1      one failure so far (dart never uses `-N:` for skips)
#   ~2      two skipped so far
# The `mm:ss` clock prefix is stripped first so its digits are not read as
# counters; the token sign must directly precede the number.
_CLOCK_RE = re.compile(r"^\d{1,2}:[0-9]{2}(?:\.[0-9]+)?")
# The sign may be followed by whitespace, and the number must not be preceded
# by another digit or a colon (so `00:02` clock digits and `(total: 45)` never
# read as counters). NOTE: the dash is escaped — `[+-~]` would be a character
# *range* from '+' (43) to '~' (126), silently matching ':' and digits too.
_TOKEN_RE = re.compile(r"(?<![0-9:])(?P<sign>[+\-~])\s*(?P<value>\d+)")
# Per-test failure markers. Two real shapes exist:
#   compact progress line: `00:02 +0 -1: add works [E]`
#   expanded listing:      `[E] add works (test/main_test.dart:7)`
_MARKER_TAIL_RE = re.compile(
    r"^(?P<name>.+?)\s*(?:\((?P<loc>[^()\s]+:\d+)\))?\s*\[E\]\s*$"
)
_MARKER_HEAD_RE = re.compile(
    r"^\[(?:E|e)\]\s+(?P<name>.+?)\s*(?:\((?P<loc>[^()\s]+:\d+)\))?$"
)
_COUNTERS_AND_COLON_RE = re.compile(r"^(?:[+-~]\s*\d+\s*)+:\s*")


def _match_failure_marker(stripped: str) -> re.Match[str] | None:
    """Match either failure-marker shape and return the named groups."""
    head = _MARKER_HEAD_RE.match(stripped)
    if head:
        return head
    probe = _CLOCK_RE.sub("", stripped, count=1).strip()
    probe = _COUNTERS_AND_COLON_RE.sub("", probe)
    return _MARKER_TAIL_RE.match(probe)


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def parse_dart_output(raw_output: str) -> tuple[int, int, int, int, list[FailureDetail]]:
    """Parse dart/flutter test console output.

    Returns ``(passed, failed, skipped, errors, failures)``.
    """
    text = _strip_ansi(raw_output)

    plus = minus = tilde = 0
    saw_any_counter = False
    saw_verdict = False
    failures: list[FailureDetail] = []
    current_failure: FailureDetail | None = None

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # -- Per-test failure markers ----------------------------------------
        mm = _match_failure_marker(stripped)
        if mm:
            name, loc = mm.group("name"), mm.group("loc")
            file_path, line_no = "", None
            if loc:
                file_path, _, ln = loc.rpartition(":")
                try:
                    line_no = int(ln)
                except ValueError:
                    file_path, line_no = loc, None
            if not any(f.test_name == name for f in failures):
                current_failure = FailureDetail(
                    test_name=name,
                    file_path=file_path,
                    line_number=line_no,
                    error_type="TestFailure",
                    suggested_fix="",
                )
                failures.append(current_failure)
            continue

        # -- Progress / verdict lines carry the cumulative counters ----------
        # Only trust tokens on lines that start with the `mm:ss` clock; free
        # prose like "Expected 4 - Actual 3" contains stray +/- digits that
        # would poison the counts.
        is_clock_line = bool(_CLOCK_RE.match(stripped))
        all_pass = bool(_ALL_PASSED_RE.search(stripped))
        some_fail = bool(_SOME_FAILED_RE.search(stripped))
        has_verdict = all_pass or some_fail
        if is_clock_line or has_verdict:
            probe = _CLOCK_RE.sub("", stripped, count=1)
            for tm_match in _TOKEN_RE.finditer(probe):
                sign = tm_match.group("sign")
                n = int(tm_match.group("value"))
                if sign == "+":
                    plus = n
                    saw_any_counter = True
                elif sign == "-":
                    minus = n
                    saw_any_counter = True
                else:
                    tilde = n
                    saw_any_counter = True
            # A bare verdict line (no clock, no counters) is still
            # machine-readable evidence that a suite ran to completion.
            saw_verdict = saw_verdict or has_verdict

            # Verdict lines end the current failure block.
            current_failure = None
            continue

        # -- Error detail body under the last [E] marker ---------------------
        if current_failure is not None:
            if not current_failure.message:
                current_failure.message = stripped
            elif len(current_failure.traceback) < 4000:
                current_failure.traceback = (
                    (current_failure.traceback + "\n" + stripped)
                    if current_failure.traceback
                    else stripped
                )

    passed, failed, skipped = plus, minus, tilde

    if not saw_any_counter and not saw_verdict and not failures:
        # Nothing machine-readable at all (crash before any suite loaded).
        # Signal "unparseable" via the errors slot; upstream reports the exit
        # code alongside, so no counts are invented here.
        return 0, 0, 0, 1, failures

    # The `(total: N)` form lets an all-green run with silent skips be
    # reconciled against the authoritative total. When the verdict is
    # all-green and the counters saw nothing, the total *is* the pass count —
    # attributing it to `skipped` would misreport a healthy run.
    tm = _TOTAL_IN_VERDICT.search(text)
    if tm:
        total = int(tm.group(1))
        accounted = passed + failed + skipped
        if failed == 0 and accounted == 0:
            passed = total
        elif total > accounted:
            skipped += total - accounted

    return passed, failed, skipped, 0, failures
