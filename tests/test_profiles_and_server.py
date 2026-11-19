"""Tests for profile selection, tool deduplication, resources, and real stdio MCP startup."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from comsol_mcp.compat import list_registered_resources, list_registered_tools
from comsol_mcp.config import ALL_PROFILES, parse_profiles
from comsol_mcp.server import build_server


def test_parse_profiles_validation() -> None:
    assert parse_profiles("all") == ALL_PROFILES
    assert parse_profiles("core, batch, core") == ("core", "batch")
    with pytest.raises(ValueError, match="Unknown COMSOL_MCP_PROFILES"):
        parse_profiles("core,nonexistent")


def test_profile_gating_tool_counts(tmp_path: Path) -> None:
    all_bundle = build_server(profiles="all", workspace=str(tmp_path / "all"), dryrun=True)
    all_tools = list_registered_tools(all_bundle.mcp)
    all_resources = list_registered_resources(all_bundle.mcp)
    assert len(all_tools) == 66
    assert len(set(all_tools)) == 66
    assert len(all_resources) == 4
    all_bundle.hub.shutdown()

    batch_only = build_server(profiles="batch", workspace=str(tmp_path / "batch"), dryrun=True)
    batch_tools = list_registered_tools(batch_only.mcp)
    assert len(batch_tools) == 10
    assert all(t.startswith("batch_") for t in batch_tools)
    batch_only.hub.shutdown()

    core_val = build_server(profiles="core,catalog,validate", workspace=str(tmp_path / "cv"), dryrun=True)
    assert len(list_registered_tools(core_val.mcp)) == 34
    core_val.hub.shutdown()


def test_cli_doctor_and_real_stdio_initialize(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["COMSOL_MCP_WORKSPACE"] = str(tmp_path / "ws")
    env["COMSOL_MCP_DRYRUN"] = "true"
    env["COMSOL_MCP_PROFILES"] = "core,batch"
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")

    # 1. CLI doctor check
    doc = subprocess.run(
        [sys.executable, "-m", "comsol_mcp", "doctor"],
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )
    payload = json.loads(doc.stdout)
    assert payload["tool_count"] == 35
    assert payload["mounted_profiles"] == ["core", "batch"]

    # 2. Real stdio JSON-RPC initialize + tools/list handshake
    proc = subprocess.Popen(
        [sys.executable, "-m", "comsol_mcp", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True,
    )
    try:
        assert proc.stdin and proc.stdout
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        }
        proc.stdin.write(json.dumps(init_req) + "\n")
        proc.stdin.flush()
        line = proc.stdout.readline()
        resp = json.loads(line)
        assert resp["id"] == 1
        assert "result" in resp
        assert "COMSOL Multiphysics Unified MCP" in resp["result"]["serverInfo"]["name"]
    finally:
        proc.terminate()
        proc.wait(timeout=10)
