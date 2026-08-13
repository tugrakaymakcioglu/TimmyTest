"""Rule-based suggestion engine for diagnosing test failures."""

import re

from timmytest.detector.models import FailureDetail


def generate_fix_suggestion(failure: FailureDetail) -> str:
    """
    Analyzes a failure detail and returns a concrete, actionable suggestion
    for the developer or AI coding agent.
    """
    msg = failure.message.lower()
    trace = failure.traceback.lower()
    err_type = failure.error_type.lower()
    combined = f"{msg} {trace} {err_type}"

    # 1. ModuleNotFoundError / ImportError
    import_match = re.search(r"no module named ['\"]([^'\"]+)['\"]", failure.message, re.IGNORECASE)
    if import_match:
        mod = import_match.group(1)
        return f"Missing dependency '{mod}'. Install it via pip/npm or check your import path."
    if "importerror" in combined or "cannot find module" in combined:
        return "Import failure: verify module exists and is included in PYTHONPATH / tsconfig paths."

    # 2. AssertionError with equality
    assert_eq_match = re.search(r"assert\s+(.+?)\s*==\s*(.+)", failure.message, re.IGNORECASE)
    if assert_eq_match:
        val1 = assert_eq_match.group(1).strip()
        val2 = assert_eq_match.group(2).strip()
        return f"Value mismatch: Expected '{val2}', got '{val1}'. Adjust implementation return value or update test assertion."

    if "assertionerror" in combined:
        return "Assertion failed: Review conditional check or assertion statement in the test."

    # 3. AttributeError (NoneType or missing member)
    if "'nonetype' object has no attribute" in combined:
        return "NoneType error: Function or variable returned None unexpectedly. Add a None check or verify mock/fixture initialization."
    attr_match = re.search(r"object has no attribute ['\"]([^'\"]+)['\"]", failure.message, re.IGNORECASE)
    if attr_match:
        attr = attr_match.group(1)
        return f"Attribute '{attr}' does not exist on target object. Verify class definition or interface."

    # 4. TypeError
    if "missing" in combined and "required positional argument" in combined:
        return "Mismatched arguments: Caller is missing required arguments. Verify function signature."
    if "unexpected keyword argument" in combined:
        return "Unexpected keyword argument passed to function. Check kwargs or parameter names."
    if "typeerror" in combined:
        return "Type mismatch: Check passed argument types against expected parameter types."

    # 5. KeyError / IndexError
    if "keyerror" in combined:
        key_match = re.search(r"keyerror:\s*['\"]?([^'\"\n]+)['\"]?", failure.message, re.IGNORECASE)
        k = key_match.group(1) if key_match else "key"
        return f"KeyError: Key '{k}' missing from dictionary. Ensure dictionary contains expected keys or use .get()."
    if "indexerror" in combined or "list index out of range" in combined:
        return "Index out of range: List is shorter than expected. Check list length before indexing."

    # 6. FileNotFoundError
    if "filenotfounderror" in combined or "no such file or directory" in combined:
        return "File not found: Verify relative path resolution (consider using Path(__file__).parent) or mock the file system."

    # 7. Timeout
    if "timeout" in combined:
        return "Execution timed out: Check for infinite loops, deadlocks, or slow network calls. Consider mocking external I/O."

    # 8. Database / Network Connection
    if "connection refused" in combined or "connectionerror" in combined:
        return "Connection error: Database or service unreachable. Mock network/DB requests in unit tests."

    # 9. Mock / Spy Failure
    if "mock" in combined or "called" in combined:
        return "Mock expectation not met: Verify mock call count, arguments, and return values."

    return "Review traceback to identify unexpected runtime behavior or unhandled edge cases."
