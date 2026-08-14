"""Tests for TimmyTest Model Context Protocol (MCP) server."""

from pathlib import Path

from timmytest.mcp.server import process_jsonrpc_message


def test_mcp_initialize():
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0"},
        },
    }
    resp = process_jsonrpc_message(msg)
    assert resp is not None
    assert resp["id"] == 1
    assert "tools" in resp["result"]["capabilities"]
    assert resp["result"]["serverInfo"]["name"] == "timmytest-mcp"


def test_mcp_tools_list():
    msg = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {},
    }
    resp = process_jsonrpc_message(msg)
    assert resp is not None
    assert resp["id"] == 2
    tools = resp["result"]["tools"]
    tool_names = [t["name"] for t in tools]
    assert "timmytest_check" in tool_names
    assert "timmytest_scan" in tool_names
    assert "timmytest_run" in tool_names
    assert "timmytest_prompt" in tool_names
    assert "timmytest_integrate" in tool_names


def test_mcp_tool_call_scan(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "core.py").write_text("def ping():\n    return 'pong'\n", encoding="utf-8")

    msg = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "timmytest_scan",
            "arguments": {"project_path": str(temp_project_dir)},
        },
    }
    resp = process_jsonrpc_message(msg)
    assert resp is not None
    assert resp["id"] == 3
    assert not resp.get("isError")
    content = resp["result"]["content"][0]["text"]
    assert "project" in content


def test_mcp_tool_call_prompt(temp_project_dir: Path):
    src_dir = temp_project_dir / "src"
    src_dir.mkdir()
    (src_dir / "service.py").write_text("class MyService:\n    def execute(self):\n        pass\n", encoding="utf-8")

    msg = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "timmytest_prompt",
            "arguments": {"project_path": str(temp_project_dir)},
        },
    }
    resp = process_jsonrpc_message(msg)
    assert resp is not None
    assert resp["id"] == 4
    content = resp["result"]["content"][0]["text"]
    assert "TimmyTest Diagnostic Handoff for AI Agent" in content


def test_mcp_tool_call_integrate(temp_project_dir: Path):
    (temp_project_dir / "pyproject.toml").write_text("[project]\nname='my-tool'\n", encoding="utf-8")

    msg = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "timmytest_integrate",
            "arguments": {"project_path": str(temp_project_dir), "force": True},
        },
    }
    resp = process_jsonrpc_message(msg)
    assert resp is not None
    assert resp["id"] == 5
    content = resp["result"]["content"][0]["text"]
    assert "Integrated TimmyTest" in content
    assert (temp_project_dir / ".cursorrules").exists()


def test_mcp_unknown_method():
    msg = {
        "jsonrpc": "2.0",
        "id": 99,
        "method": "unknown_method",
        "params": {},
    }
    resp = process_jsonrpc_message(msg)
    assert resp is not None
    assert resp["id"] == 99
    assert resp["error"]["code"] == -32601
