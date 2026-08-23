"""Lightweight, zero-dependency stdio MCP (Model Context Protocol) server for TimmyTest.

Allows Cursor, Claude Code, Claude Desktop, Antigravity, and Zed to invoke TimmyTest
tools natively with zero token waste and zero terminal scraping.
"""

import json
import sys
from pathlib import Path
from typing import Any

from timmytest import __version__
from timmytest.analysis import analyze_project
from timmytest.integrations.installer import integrate_project
from timmytest.reports.json_export import export_audit_to_json

#: Ceiling for the client-supplied timeout: an agent that asks for a two-hour
#: run would otherwise wedge the server, which serves one request at a time.
MAX_TOOL_TIMEOUT = 900
DEFAULT_TOOL_TIMEOUT = 120


def _timeout_arg(arguments: dict[str, Any]) -> int:
    """Clamp the caller's timeout into a sane range, tolerating bad input."""
    try:
        value = int(arguments.get("timeout_seconds") or DEFAULT_TOOL_TIMEOUT)
    except (TypeError, ValueError):
        return DEFAULT_TOOL_TIMEOUT
    return max(5, min(value, MAX_TOOL_TIMEOUT))


TOOLS_DEFINITIONS = [
    {
        "name": "timmytest_check",
        "description": "Run a comprehensive zero-token test audit on a repository. Executes tests locally, discovers missing AST test gaps, diagnoses failures with fix suggestions, and returns a dense AI prompt.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Absolute or relative path to target project directory (default: '.')",
                    "default": ".",
                },
                "filter_pattern": {
                    "type": "string",
                    "description": "Optional filter keyword for test names (e.g. 'auth')",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Test execution timeout in seconds (default: 60)",
                    "default": 60,
                },
            },
        },
    },
    {
        "name": "timmytest_scan",
        "description": "Fast static AST code inspection without executing tests. Identifies untested classes, functions, and missing test files.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to target project directory (default: '.')",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "timmytest_run",
        "description": "Execute tests and isolate only failing tests with rule-based diagnostic fix suggestions.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to target project directory (default: '.')",
                    "default": ".",
                },
                "filter_pattern": {
                    "type": "string",
                    "description": "Optional filter keyword for test names",
                },
                "timeout_seconds": {
                    "type": "integer",
                    "description": "Test execution timeout in seconds (default: 60)",
                    "default": 60,
                },
            },
        },
    },
    {
        "name": "timmytest_prompt",
        "description": "Generate an ultra-dense, token-optimized diagnostic prompt for fixing bugs or writing missing tests.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to target project directory (default: '.')",
                    "default": ".",
                },
            },
        },
    },
    {
        "name": "timmytest_integrate",
        "description": "Setup and install AI agent instruction rules (.cursorrules, CLAUDE.md, AGENTS.md, copilot rules) and TimmyTest config in the project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project_path": {
                    "type": "string",
                    "description": "Path to target project directory (default: '.')",
                    "default": ".",
                },
                "force": {
                    "type": "boolean",
                    "description": "Re-integrate even if TimmyTest rules are already present (appends; never overwrites existing content)",
                    "default": False,
                },
            },
        },
    },
]


#: MCP tool -> the switch that governs the same capability on the CLI. Without
#: this the switches would only be half-honoured: turning `cli.integrate` off
#: would stop the command while leaving an agent free to do the same thing
#: through the MCP server.
_TOOL_FEATURES = {
    "timmytest_check": "cli.check",
    "timmytest_scan": "cli.scan",
    "timmytest_run": "cli.run",
    "timmytest_prompt": "cli.prompt",
    "timmytest_integrate": "cli.integrate",
}


def _handle_tool_call(name: str, arguments: dict[str, Any]) -> str:
    """Execute the requested tool and return a string result."""
    from timmytest import flags

    feature = _TOOL_FEATURES.get(name)
    if feature is not None and not flags.is_enabled(feature):
        return f"Error: '{feature}' is switched off for this TimmyTest install."

    project_dir = Path(arguments.get("project_path", ".")).resolve()
    if not project_dir.exists():
        return f"Error: Project path '{project_dir}' does not exist."

    # Every analysis tool routes through the one shared orchestrator, so an MCP
    # client gets exactly what the CLI would produce - including the project's
    # own .timmytest.yml (custom command, ignore lists, timeout), which the
    # previous hand-rolled copies in this module silently ignored.
    if name == "timmytest_check":
        audit = analyze_project(
            project_dir=project_dir,
            execute_tests=True,
            timeout_seconds=_timeout_arg(arguments),
            filter_pattern=arguments.get("filter_pattern"),
        )
        return audit.agent_prompt

    elif name == "timmytest_scan":
        audit = analyze_project(project_dir=project_dir, execute_tests=False)
        return export_audit_to_json(audit)

    elif name == "timmytest_run":
        audit = analyze_project(
            project_dir=project_dir,
            execute_tests=True,
            timeout_seconds=_timeout_arg(arguments),
            filter_pattern=arguments.get("filter_pattern"),
        )
        test_run = audit.test_run
        if not test_run.has_executed:
            return "No test files were found in this project, so nothing was executed."

        out: list[str] = [
            f"Test Execution: {test_run.passed} Passed, {test_run.failed} Failed, "
            f"{test_run.errors} Suite Errors, {test_run.skipped} Skipped "
            f"(Total: {test_run.total}, exit code {test_run.exit_code})",
        ]
        if test_run.failures:
            out.append(f"\nFailures ({len(test_run.failures)}):")
            for f in test_run.failures:
                loc = f" ({f.file_path}:{f.line_number})" if f.file_path and f.line_number else ""
                out.append(f"- {f.test_name}{loc}: [{f.error_type}] {f.message}")
                if f.suggested_fix:
                    out.append(f"  Fix: {f.suggested_fix}")
        return "\n".join(out)

    elif name == "timmytest_prompt":
        audit = analyze_project(project_dir=project_dir, execute_tests=False)
        return audit.agent_prompt

    elif name == "timmytest_integrate":
        force = arguments.get("force", False)
        result = integrate_project(project_dir, force=force)
        created = [str(p.relative_to(project_dir)) for p in result.created_files]
        modified = [str(p.relative_to(project_dir)) for p in result.modified_files]
        return f"Integrated TimmyTest! Created: {created}, Modified: {modified}"

    return f"Unknown tool: {name}"


def process_jsonrpc_message(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Process a single JSON-RPC message and return the response dictionary."""
    msg_id = msg.get("id")
    method = msg.get("method")
    params = msg.get("params", {})

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {},
                },
                "serverInfo": {
                    "name": "timmytest-mcp",
                    "version": __version__,
                },
            },
        }

    elif method == "notifications/initialized":
        # Notification, no response needed
        return None

    elif method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {},
        }

    elif method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "tools": TOOLS_DEFINITIONS,
            },
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        try:
            output = _handle_tool_call(tool_name, tool_args)
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": output,
                        }
                    ]
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Error running {tool_name}: {exc}",
                        }
                    ],
                    "isError": True,
                },
            }

    # Method not found
    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }
    return None


def run_mcp_server() -> None:
    """Run the stdio MCP server loop."""
    # MCP is a UTF-8 protocol, but a pipe on Windows inherits the console code
    # page (cp1254 on Turkish systems), so a project path with an accented
    # character could raise UnicodeDecodeError and kill the server mid-session.
    import contextlib

    for stream in (sys.stdin, sys.stdout):
        if hasattr(stream, "reconfigure"):
            with contextlib.suppress(Exception):
                stream.reconfigure(encoding="utf-8", errors="replace")

    sys.stderr.write(f"Starting TimmyTest MCP Server v{__version__} on stdio...\n")
    sys.stderr.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = process_jsonrpc_message(req)
            if resp is not None:
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()
        except Exception as exc:
            sys.stderr.write(f"Error handling message: {exc}\n")
            sys.stderr.flush()
