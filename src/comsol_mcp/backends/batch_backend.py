"""Native COMSOL Java/batch async job queue backend (`comsolcompile` + `comsolbatch`).

Provides isolated per-job compilation and execution without requiring `mph` or
JPype, with strict workspace confinement, non-destructive copy-on-edit outputs,
completion-marker verification, hard process-tree timeouts, and workspace locking.
"""

from __future__ import annotations

import json
import os
import platform
import re
import signal
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Optional

from ..config import Settings
from .base import confined_path, java_string

_TERMINAL_STATES = {"succeeded", "failed", "cancelled", "interrupted"}
_ACTIVE_STATES = {"queued", "compiling", "running"}
_ALLOWED_ARTIFACT_SUFFIXES = {".java", ".txt", ".csv", ".log", ".json"}


def _terminate_process_tree(proc: subprocess.Popen[Any]) -> None:
    """Terminate a child process and its full descendant tree."""
    if proc.poll() is not None:
        return
    if platform.system() == "Windows":
        subprocess.run(
            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=30,
            check=False,
        )
    else:  # pragma: no cover - POSIX branch
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=30)
    except subprocess.TimeoutExpired:
        proc.kill()


class BatchJobBackend:
    """Single-worker asynchronous job queue backed by native COMSOL CLI binaries."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root: Path = settings.workspace.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs_dir: Path = self.root / ".jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)

        self._lock = threading.RLock()
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="comsol-batch")
        self._active: dict[str, subprocess.Popen[Any]] = {}
        self._cancelled: set[str] = set()
        self._workspace_lock_handle: Any = None

    def acquire_workspace_lock(self) -> None:
        """Prevent multiple server instances from managing the same batch workspace."""
        if self._workspace_lock_handle is not None:
            return
        lock_file = self.jobs_dir / "server.lock"
        handle = lock_file.open("a+b")
        try:
            handle.seek(0)
            if lock_file.stat().st_size == 0:
                handle.write(b"0")
                handle.flush()
                handle.seek(0)
            if platform.system() == "Windows":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:  # pragma: no cover - POSIX branch
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            handle.close()
            raise RuntimeError(
                f"Workspace '{self.root}' is locked by another COMSOL MCP server. Set COMSOL_MCP_WORKSPACE to a separate directory."
            ) from exc

        self._workspace_lock_handle = handle
        self._mark_stale_jobs_interrupted()

    def _mark_stale_jobs_interrupted(self) -> None:
        for status_path in self.jobs_dir.glob("*/status.json"):
            try:
                data = json.loads(status_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("state") in _ACTIVE_STATES:
                self._update_status(
                    status_path.parent,
                    state="interrupted",
                    error="Server restarted while job was unfinished; inspect logs before resubmitting.",
                )

    def release_workspace_lock(self) -> None:
        if self._workspace_lock_handle is not None:
            try:
                self._workspace_lock_handle.close()
            finally:
                self._workspace_lock_handle = None

    def shutdown(self) -> None:
        """Cancel unfinished jobs and terminate active subprocess trees."""
        with self._lock:
            for status_path in self.jobs_dir.glob("*/status.json"):
                try:
                    data = json.loads(status_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if data.get("state") in _ACTIVE_STATES:
                    jid = data.get("id", status_path.parent.name)
                    self._cancelled.add(jid)
                    self._update_status(status_path.parent, state="cancelled", error="Server shutting down.")
            procs = list(self._active.items())
            self._cancelled.update(jid for jid, _ in procs)
            self._pool.shutdown(wait=False, cancel_futures=True)
        for _, proc in procs:
            _terminate_process_tree(proc)
        self.release_workspace_lock()

    def status(self) -> dict[str, Any]:
        compile_bin = self.settings.comsol_binary("comsolcompile")
        batch_bin = self.settings.comsol_binary("comsolbatch")
        return {
            "backend": "batch",
            "platform": platform.system(),
            "comsol_home": str(self.settings.comsol_home) if self.settings.comsol_home else None,
            "comsolcompile": str(compile_bin) if compile_bin else None,
            "comsolbatch": str(batch_bin) if batch_bin else None,
            "ready": bool(compile_bin and batch_bin),
            "workspace": str(self.root),
            "cores": self.settings.cores,
            "active_jobs": sorted(self._active.keys()),
            "license_note": "Binary discovery confirms installation only; license availability is verified when a job succeeds.",
        }

    def list_models(self) -> list[dict[str, Any]]:
        return sorted(
            [
                {"file": str(p.relative_to(self.root)).replace("\\", "/"), "bytes": p.stat().st_size}
                for p in self.root.rglob("*.mph")
                if not p.is_relative_to(self.jobs_dir)
            ],
            key=lambda item: item["file"],
        )

    def get_template(self, name: str = "block") -> dict[str, Any]:
        templates_dir = self.settings.repo_root / "examples" / "java"
        valid = sorted(p.name.removesuffix(".java.txt") for p in templates_dir.glob("*.java.txt"))
        if name not in valid:
            raise ValueError(f"Unknown template '{name}'. Available templates: {valid}")
        content = (templates_dir / f"{name}.java.txt").read_text(encoding="utf-8")
        return {"name": name, "available": valid, "java_body": content}

    def _job_dir(self, job_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{32}", job_id):
            raise ValueError(f"Invalid job ID: '{job_id}'")
        directory = self.jobs_dir / job_id
        if not (directory / "status.json").is_file():
            raise ValueError(f"Unknown job ID: '{job_id}'")
        return directory

    def _update_status(self, directory: Path, **updates: Any) -> dict[str, Any]:
        with self._lock:
            target = directory / "status.json"
            state = json.loads(target.read_text(encoding="utf-8")) if target.is_file() else {}
            state.update(updates, updated=time.time())
            tmp = directory / "status.tmp"
            tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
            tmp.replace(target)
            return state

    def run_subprocess(self, job_id: str, command: list[str], log_path: Path, deadline: float) -> None:
        """Execute a command with bounded deadline, logging, and tree-kill cancellation."""
        kwargs: dict[str, Any] = {
            "cwd": str(log_path.parent),
            "stderr": subprocess.STDOUT,
        }
        if platform.system() == "Windows":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:  # pragma: no cover - POSIX branch
            kwargs["start_new_session"] = True

        with log_path.open("wb") as sink:
            with self._lock:
                if job_id in self._cancelled:
                    raise RuntimeError("Job cancelled before launch.")
                proc = subprocess.Popen(command, stdout=sink, **kwargs)
                self._active[job_id] = proc
            try:
                remaining = max(0.1, deadline - time.monotonic())
                rc = proc.wait(timeout=remaining)
                if job_id in self._cancelled:
                    raise RuntimeError("Job cancelled.")
                if rc != 0:
                    raise RuntimeError(f"Process exited with code {rc}; inspect '{log_path.name}'.")
            except subprocess.TimeoutExpired as exc:
                _terminate_process_tree(proc)
                raise TimeoutError("Job exceeded timeout; subprocess tree terminated.") from exc
            finally:
                with self._lock:
                    self._active.pop(job_id, None)

    def _worker(self, job_id: str, output_path: Path, timeout_seconds: int) -> None:
        directory = self._job_dir(job_id)
        deadline = time.monotonic() + timeout_seconds
        try:
            compile_bin = self.settings.comsol_binary("comsolcompile")
            batch_bin = self.settings.comsol_binary("comsolbatch")
            if not compile_bin or not batch_bin:
                raise RuntimeError("COMSOL binaries (comsolcompile/comsolbatch) not found. Set COMSOL_HOME.")

            self._update_status(directory, state="compiling")
            self.run_subprocess(
                job_id,
                [str(compile_bin), str(directory / "McpModel.java")],
                directory / "compile.log",
                deadline,
            )
            if not (directory / "McpModel.class").is_file():
                raise RuntimeError("Compiler produced no McpModel.class; inspect compile.log.")

            self._update_status(directory, state="running")
            prefs_dir = directory / "prefs"
            prefs_dir.mkdir(exist_ok=True)
            (prefs_dir / "comsol.prefs").write_text("security.external.filepermission=full\n", encoding="utf-8")

            with tempfile.TemporaryDirectory(prefix="cmcp_") as scratch:
                self.run_subprocess(
                    job_id,
                    [
                        str(batch_bin),
                        "-np",
                        str(self.settings.cores),
                        "-prefsdir",
                        str(prefs_dir),
                        "-3drend",
                        "sw",
                        "-autosave",
                        "off",
                        "-tmpdir",
                        scratch,
                        "-recoverydir",
                        scratch,
                        "-inputfile",
                        str(directory / "McpModel.class"),
                        "-batchlog",
                        str(directory / "batch.log"),
                    ],
                    directory / "process.log",
                    deadline,
                )

            staged = directory / "result.mph"
            combined_logs = "\n".join(
                p.read_text(encoding="utf-8", errors="replace") for p in directory.glob("*.log")
            )
            marker = f"MCP_MODEL_SAVED_{job_id}"
            if marker not in combined_logs:
                raise RuntimeError(
                    "Completion marker not found in logs (COMSOL may return exit code 0 after a model exception)."
                )
            if not staged.is_file() or staged.stat().st_size == 0:
                raise RuntimeError("COMSOL did not save a non-empty result.mph; inspect batch.log.")

            with self._lock:
                if job_id in self._cancelled:
                    raise RuntimeError("Job cancelled before publication.")
                output_path.parent.mkdir(parents=True, exist_ok=True)
                if output_path.exists():
                    raise FileExistsError(f"Destination '{output_path}' already exists; refusing to overwrite.")
                staged.rename(output_path)
                self._update_status(
                    directory,
                    state="succeeded",
                    output=str(output_path),
                    bytes=output_path.stat().st_size,
                )
        except Exception as exc:
            final_state = "cancelled" if job_id in self._cancelled else "failed"
            self._update_status(directory, state=final_state, error=str(exc))

    def submit(
        self,
        java_body: str,
        output_file: str,
        *,
        input_file: Optional[str] = None,
        timeout_seconds: int = 600,
        require_binaries: bool = True,
        launch_worker: bool = True,
    ) -> dict[str, Any]:
        """Validate paths, generate McpModel.java wrapper, and enqueue an isolated batch job."""
        if require_binaries and not (
            self.settings.comsol_binary("comsolcompile") and self.settings.comsol_binary("comsolbatch")
        ):
            raise RuntimeError("COMSOL binaries not found. Set COMSOL_HOME to your Multiphysics directory.")
        if not 30 <= int(timeout_seconds) <= 86400:
            raise ValueError("timeout_seconds must be between 30 and 86400.")

        output = confined_path(self.root, output_file, forbidden_subdir=self.jobs_dir, suffix=".mph")
        if output.exists():
            raise ValueError(f"Output '{output_file}' already exists. Choose a new versioned filename.")
        source = (
            confined_path(self.root, input_file, forbidden_subdir=self.jobs_dir, suffix=".mph", must_exist=True)
            if input_file
            else None
        )

        job_id = uuid.uuid4().hex
        directory = self.jobs_dir / job_id
        directory.mkdir(parents=True, exist_ok=False)

        init_expr = f'ModelUtil.load("Model", {java_string(str(source))})' if source else 'ModelUtil.create("Model")'
        wrapper = (
            "import com.comsol.model.*;\n"
            "import com.comsol.model.util.*;\n"
            "public class McpModel {\n"
            "  public static Model run() throws Exception {\n"
            f"    Model model = {init_expr};\n"
            f"    model.modelPath({java_string(str(directory))});\n"
            f"    model.label({java_string(output.name)});\n"
            f"{java_body}\n"
            f'    model.save({java_string(str(directory / "result.mph"))});\n'
            f'    System.out.println("MCP_MODEL_SAVED_{job_id}");\n'
            "    return model;\n"
            "  }\n"
            "  public static void main(String[] args) throws Exception { run(); }\n"
            "}\n"
        )
        (directory / "McpModel.java").write_text(wrapper, encoding="utf-8")
        state = self._update_status(
            directory,
            id=job_id,
            state="queued",
            requested_output=str(output),
            input=str(source) if source else None,
            created=time.time(),
        )
        if launch_worker:
            self._pool.submit(self._worker, job_id, output, int(timeout_seconds))
        return state

    def job_status(self, job_id: str, tail_characters: int = 12000) -> dict[str, Any]:
        directory = self._job_dir(job_id)
        if not 0 <= int(tail_characters) <= 50000:
            raise ValueError("tail_characters must be between 0 and 50000.")
        with self._lock:
            state = json.loads((directory / "status.json").read_text(encoding="utf-8"))
        state["logs"] = {
            p.name: p.read_text(encoding="utf-8", errors="replace")[-tail_characters:] if tail_characters else ""
            for p in sorted(directory.glob("*.log"))
        }
        state["artifacts"] = sorted(p.name for p in directory.iterdir() if p.is_file())
        return state

    def list_jobs(self, limit: int = 20) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for status_path in self.jobs_dir.glob("*/status.json"):
            try:
                rows.append(json.loads(status_path.read_text(encoding="utf-8")))
            except Exception:
                continue
        rows.sort(key=lambda r: r.get("created", 0), reverse=True)
        return rows[: max(1, limit)]

    def read_artifact(self, job_id: str, filename: str, offset: int = 0, limit: int = 16000) -> dict[str, Any]:
        directory = self._job_dir(job_id)
        path = (directory / filename).resolve()
        if path.parent != directory or path.suffix.lower() not in _ALLOWED_ARTIFACT_SUFFIXES:
            raise ValueError(f"Only text artifacts ({sorted(_ALLOWED_ARTIFACT_SUFFIXES)}) directly in the job directory may be read.")
        if not path.is_file():
            raise FileNotFoundError(f"Artifact '{filename}' not found in job '{job_id}'.")
        if offset < 0 or not 1 <= int(limit) <= 50000:
            raise ValueError("Invalid offset or limit (limit must be 1..50000).")
        with path.open(encoding="utf-8", errors="replace") as stream:
            stream.read(offset)
            text = stream.read(limit)
            has_more = bool(stream.read(1))
        return {"filename": filename, "text": text, "next_offset": offset + len(text), "has_more": has_more}

    def cancel_job(self, job_id: str) -> dict[str, Any]:
        directory = self._job_dir(job_id)
        with self._lock:
            state = json.loads((directory / "status.json").read_text(encoding="utf-8"))
            if state.get("state") in _TERMINAL_STATES:
                return state
            self._cancelled.add(job_id)
            proc = self._active.get(job_id)
        if proc is not None:
            _terminate_process_tree(proc)
        return self._update_status(directory, state="cancelled")
