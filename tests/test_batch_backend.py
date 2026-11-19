"""Tests for native batch backend controls: path confinement, copy-on-edit, locking, timeout kill, cancel."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

from comsol_mcp.backends.batch_backend import BatchJobBackend
from comsol_mcp.config import Settings


def _make_batch(tmp_path: Path) -> BatchJobBackend:
    ws = tmp_path / "models"
    ws.mkdir(exist_ok=True)
    cfg = Settings(
        repo_root=Path(__file__).resolve().parents[1],
        workspace=ws,
        catalog_dir=tmp_path / "cat",
        pdf_dir=tmp_path / "pdf",
        knowledge_dir=tmp_path / "kb",
    )
    return BatchJobBackend(cfg)


def test_path_confinement_and_no_overwrite(tmp_path: Path) -> None:
    batch = _make_batch(tmp_path)
    try:
        # Path traversal outside workspace rejected
        with pytest.raises(ValueError, match="must stay inside workspace"):
            batch.submit("", "../escape.mph", require_binaries=False, launch_worker=False)

        # Writing inside .jobs rejected
        with pytest.raises(ValueError, match="cannot target internal directory"):
            batch.submit("", ".jobs/bad.mph", require_binaries=False, launch_worker=False)

        # Wrong suffix rejected
        with pytest.raises(ValueError, match="Expected a '.mph'"):
            batch.submit("", "model.txt", require_binaries=False, launch_worker=False)

        # Existing output file rejected (copy-on-edit immutability)
        existing = batch.root / "existing.mph"
        existing.write_bytes(b"original")
        with pytest.raises(ValueError, match="already exists"):
            batch.submit("", "existing.mph", require_binaries=False, launch_worker=False)
    finally:
        batch.shutdown()


def test_templates_and_queued_cancellation_and_artifact_paging(tmp_path: Path) -> None:
    batch = _make_batch(tmp_path)
    try:
        tpl = batch.get_template("block")
        assert "Block" in tpl["java_body"]
        assert "heat_transfer" in tpl["available"]

        job = batch.submit(tpl["java_body"], "blk.mph", require_binaries=False, launch_worker=False)
        jid = job["id"]
        assert job["state"] == "queued"

        # Read generated McpModel.java in pages
        page1 = batch.read_artifact(jid, "McpModel.java", offset=0, limit=120)
        assert "public class McpModel" in page1["text"]
        assert page1["has_more"] is True
        page2 = batch.read_artifact(jid, "McpModel.java", offset=page1["next_offset"], limit=5000)
        assert f"MCP_MODEL_SAVED_{jid}" in page2["text"]

        # Cancel queued job
        cancelled = batch.cancel_job(jid)
        assert cancelled["state"] == "cancelled"
        status = batch.job_status(jid)
        assert status["state"] == "cancelled"
    finally:
        batch.shutdown()


def test_real_subprocess_timeout_termination(tmp_path: Path) -> None:
    batch = _make_batch(tmp_path)
    try:
        job = batch.submit("// noop", "timeout_test.mph", require_binaries=False, launch_worker=False)
        jid = job["id"]
        log_path = batch.jobs_dir / jid / "sleep.log"
        t0 = time.monotonic()
        with pytest.raises(TimeoutError, match="subprocess tree terminated"):
            batch.run_subprocess(
                jid,
                [sys.executable, "-c", "import time; time.sleep(30)"],
                log_path,
                deadline=time.monotonic() + 0.6,
            )
        elapsed = time.monotonic() - t0
        assert elapsed < 10.0
    finally:
        batch.shutdown()


def test_workspace_lock_blocks_second_instance(tmp_path: Path) -> None:
    b1 = _make_batch(tmp_path)
    b2 = _make_batch(tmp_path)
    try:
        b1.acquire_workspace_lock()
        with pytest.raises(RuntimeError, match="locked by another"):
            b2.acquire_workspace_lock()
    finally:
        b1.shutdown()
        b2.shutdown()
