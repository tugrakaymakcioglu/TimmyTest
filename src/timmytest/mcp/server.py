"""Lightweight, zero-dependency stdio MCP (Model Context Protocol) server for TimmyTest.

Allows Cursor, Claude Code, Claude Desktop, Antigravity, and Zed to invoke TimmyTest
tools natively with zero token waste and zero terminal scraping.
"""

import json
import sys
from pathlib import Path
from typing import Any

from timmytest import __version__
from timmytest.detector.ecosystem import detect_ecosystem
from timmytest.detector.gap_analyzer import analyze_test_gaps
from timmytest.detector.models import ProjectInfo, TestRunResult
from timmytest.detector.scanner import scan_project_structure
from timmytest.diagnostics.analyzer import enrich_test_failures
from timmytest.integrations.installer import integrate_project
from timmytest.prompt.generator import generate_agent_prompt
from timmytest.reports.json_export import export_audit_to_json
from timmytest.runner.orchestrator import run_project_tests

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

    if name == "timmytest_check":
        ecosystem, framework, default_cmd, configs = detect_ecosystem(project_dir)
        source_modules, test_modules = scan_project_structure(project_dir, ecosystem, framework)
        gaps, score = analyze_test_gaps(source_modules, test_modules, ecosystem, project_dir)

        proj_info = ProjectInfo(
            root_dir=str(project_dir),
            project_name=project_dir.name,
            ecosystem=ecosystem,
            test_framework=framework,
            config_files=configs,
            test_command=default_cmd,
            source_modules=source_modules,
            test_modules=test_modules,
            test_gaps=gaps,
            total_source_files=len(source_modules),
            total_test_files=len(test_modules),
            readiness_score=score,
        )

        timeout = arguments.get("timeout_seconds", 60)
        filter_pat = arguments.get("filter_pattern")

        if test_modules:
            test_run = run_project_tests(
                root_dir=project_dir,
                ecosystem=ecosystem,
                framework=framework,
                custom_cmd=default_cmd,
                timeout_seconds=timeout,
                filter_pattern=filter_pat,
            )
            test_run = enrich_test_failures(test_run)
        else:
            test_run = TestRunResult(
                ecosystem=ecosystem,
                framework=framework,
                command=default_cmd,
                total=0,
                has_executed=False,
            )

        prompt = generate_agent_prompt(proj_info, test_run)
        return prompt

    elif name == "timmytest_scan":
        ecosystem, framework, default_cmd, configs = detect_ecosystem(project_dir)
        source_modules, test_modules = scan_project_structure(project_dir, ecosystem, framework)
        gaps, score = analyze_test_gaps(source_modules, test_modules, ecosystem, project_dir)

        proj_info = ProjectInfo(
            root_dir=str(project_dir),
            project_name=project_dir.name,
            ecosystem=ecosystem,
            test_framework=framework,
            config_files=configs,
            test_command=default_cmd,
            source_modules=source_modules,
            test_modules=test_modules,
            test_gaps=gaps,
            total_source_files=len(source_modules),
            total_test_files=len(test_modules),
            readiness_score=score,
        )
        test_run = TestRunResult(
            ecosystem=ecosystem, framework=framework, command=default_cmd, total=0, has_executed=False
        )
        from timmytest.detector.models import ProjectAudit

        audit = ProjectAudit(project=proj_info, test_run=test_run, agent_prompt="")
        return export_audit_to_json(audit)

    elif name == "timmytest_run":
        ecosystem, framework, default_cmd, _ = detect_ecosystem(project_dir)
        timeout = arguments.get("timeout_seconds", 60)
        filter_pat = arguments.get("filter_pattern")

        test_run = run_project_tests(
            root_dir=project_dir,
            ecosystem=ecosystem,
            framework=framework,
            custom_cmd=default_cmd,
            timeout_seconds=timeout,
            filter_pattern=filter_pat,
        )
        test_run = enrich_test_failures(test_run)

        # Build clean failure output
        out: list[str] = [
            f"Test Execution: {test_run.passed} Passed, {test_run.failed} Failed, {test_run.skipped} Skipped (Total: {test_run.total})",
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
        ecosystem, framework, default_cmd, configs = detect_ecosystem(project_dir)
        source_modules, test_modules = scan_project_structure(project_dir, ecosystem, framework)
        gaps, score = analyze_test_gaps(source_modules, test_modules, ecosystem, project_dir)

        proj_info = ProjectInfo(
            root_dir=str(project_dir),
            project_name=project_dir.name,
            ecosystem=ecosystem,
            test_framework=framework,
            config_files=configs,
            test_command=default_cmd,
            source_modules=source_modules,
            test_modules=test_modules,
            test_gaps=gaps,
            total_source_files=len(source_modules),
            total_test_files=len(test_modules),
            readiness_score=score,
        )
        test_run = TestRunResult(
            ecosystem=ecosystem, framework=framework, command=default_cmd, total=0, has_executed=False
        )
        return generate_agent_prompt(proj_info, test_run)

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
