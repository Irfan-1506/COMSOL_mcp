"""Local stdio MCP bridge to the native COMSOL Java/batch API (Windows)."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from mcp.server.mcpserver import MCPServer

BASE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("COMSOL_MCP_WORKSPACE", str(BASE / "models"))).resolve()
ROOT.mkdir(parents=True, exist_ok=True)
JOBS = ROOT / ".jobs"
JOBS.mkdir(exist_ok=True)
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=1, thread_name_prefix="comsol")
ACTIVE: dict[str, subprocess.Popen] = {}
CANCELLED: set[str] = set()


def installation() -> Path:
    configured = os.environ.get("COMSOL_HOME")
    candidates = [Path(configured)] if configured else sorted(
        Path(os.environ.get("ProgramFiles", "C:/Program Files")).glob("COMSOL/COMSOL*/Multiphysics"), reverse=True
    )
    for home in candidates:
        if (home / "bin/win64/comsolbatch.exe").is_file():
            return home.resolve()
    raise RuntimeError("COMSOL not found. Set COMSOL_HOME to the Multiphysics installation directory.")


def confined(name: str, suffix: str | None = None, exists: bool = False) -> Path:
    path = (ROOT / name).resolve()
    if not path.is_relative_to(ROOT) or path == ROOT or path.is_relative_to(JOBS):
        raise ValueError("Use a file inside the model workspace, outside .jobs.")
    if suffix and path.suffix.lower() != suffix:
        raise ValueError(f"Expected a {suffix} file.")
    if exists and not path.is_file():
        raise FileNotFoundError(str(path))
    return path


def java_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def job_dir(job_id: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}", job_id):
        raise ValueError("Invalid job ID")
    directory = JOBS / job_id
    if not (directory / "status.json").exists():
        raise ValueError("Unknown job ID")
    return directory


def update(directory: Path, **values) -> dict:
    with LOCK:
        target = directory / "status.json"
        state = json.loads(target.read_text()) if target.exists() else {}
        state.update(values, updated=time.time())
        temporary = directory / "status.tmp"
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(target)
        return state


def kill(process: subprocess.Popen) -> None:
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
        process.wait(timeout=30)


def execute(job_id: str, command: list[str], log: Path, deadline: float) -> None:
    with log.open("wb") as output:
        with LOCK:
            if job_id in CANCELLED:
                raise RuntimeError("Cancelled")
            process = subprocess.Popen(command, cwd=log.parent, stdout=output,
                                       stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            ACTIVE[job_id] = process
        try:
            code = process.wait(timeout=max(0.1, deadline - time.monotonic()))
            if job_id in CANCELLED:
                raise RuntimeError("Cancelled")
            if code:
                raise RuntimeError(f"COMSOL exited with code {code}; inspect job logs.")
        except subprocess.TimeoutExpired:
            kill(process)
            raise TimeoutError("Job exceeded its timeout; process tree terminated.")
        finally:
            with LOCK:
                ACTIVE.pop(job_id, None)


def worker(job_id: str, output: Path, timeout: int) -> None:
    directory = job_dir(job_id)
    deadline = time.monotonic() + timeout
    try:
        binary = installation() / "bin/win64"
        update(directory, state="compiling")
        execute(job_id, [str(binary / "comsolcompile.exe"), str(directory / "McpModel.java")],
                directory / "compile.log", deadline)
        if not (directory / "McpModel.class").exists():
            raise RuntimeError("Compiler produced no class file; inspect compile.log.")
        update(directory, state="running")
        preferences = directory / "prefs"
        preferences.mkdir(exist_ok=True)
        (preferences / "comsol.prefs").write_text("security.external.filepermission=full\n", encoding="utf-8")
        # Native solver recovery filenames exceed MAX_PATH under long project paths.
        # A dedicated short OS temporary directory keeps these paths supported.
        with tempfile.TemporaryDirectory(prefix="cmcp_") as scratch:
            execute(job_id, [str(binary / "comsolbatch.exe"), "-np", os.environ.get("COMSOL_MCP_CORES", "2"),
                             "-prefsdir", str(preferences), "-3drend", "sw", "-autosave", "off",
                             "-tmpdir", scratch, "-recoverydir", scratch,
                             "-inputfile", str(directory / "McpModel.class"),
                             "-batchlog", str(directory / "batch.log")], directory / "process.log", deadline)
        staged = directory / "result.mph"
        logs = "\n".join(p.read_text(errors="replace") for p in directory.glob("*.log"))
        if f"MCP_MODEL_SAVED_{job_id}" not in logs:
            raise RuntimeError("Model code did not complete; inspect job logs (COMSOL can exit zero after errors).")
        if not staged.is_file() or staged.stat().st_size == 0:
            raise RuntimeError("COMSOL did not save a model; inspect batch.log.")
        with LOCK:
            if job_id in CANCELLED:
                raise RuntimeError("Cancelled")
            output.parent.mkdir(parents=True, exist_ok=True)
            # Same-volume atomic publication: never expose a partially copied MPH.
            # Windows rename fails if the destination exists, preserving prior files.
            staged.rename(output)
            update(directory, state="succeeded", output=str(output), bytes=output.stat().st_size)
    except Exception as error:
        update(directory, state="cancelled" if job_id in CANCELLED else "failed", error=str(error))


def submit(body: str, output_file: str, input_file: str | None, timeout_seconds: int) -> dict:
    installation()
    if not 30 <= timeout_seconds <= 86400:
        raise ValueError("timeout_seconds must be between 30 and 86400")
    output = confined(output_file, ".mph")
    if output.exists():
        raise ValueError("Output already exists. Choose a new filename to preserve your model.")
    source = confined(input_file, ".mph", True) if input_file else None
    job_id = uuid.uuid4().hex
    directory = JOBS / job_id
    directory.mkdir()
    init = f'ModelUtil.load("Model", {java_string(str(source))})' if source else 'ModelUtil.create("Model")'
    code = f'''import com.comsol.model.*;
import com.comsol.model.util.*;
public class McpModel {{
  public static Model run() throws Exception {{
    Model model = {init};
    model.modelPath({java_string(str(directory))});
    model.label({java_string(output.name)});
    {body}
    model.save({java_string(str(directory / "result.mph"))});
    System.out.println("MCP_MODEL_SAVED_{job_id}");
    return model;
  }}
  public static void main(String[] args) throws Exception {{ run(); }}
}}
'''
    (directory / "McpModel.java").write_text(code, encoding="utf-8")
    state = update(directory, id=job_id, state="queued", requested_output=str(output),
                   input=str(source) if source else None, created=time.time())
    POOL.submit(worker, job_id, output, timeout_seconds)
    return state


def acquire_workspace():
    """Prevent two stdio server processes from owning the same job queue."""
    import msvcrt
    handle = (JOBS / "server.lock").open("a+b")
    handle.seek(0)
    if not handle.read(1):
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        handle.close()
        raise RuntimeError("Another COMSOL MCP server owns this workspace. Use a different COMSOL_MCP_WORKSPACE.")
    for previous in JOBS.glob("*/status.json"):
        state = json.loads(previous.read_text())
        if state.get("state") in {"queued", "compiling", "running"}:
            update(previous.parent, state="interrupted", error="Server restarted; check logs before resubmitting.")
    return handle

mcp = MCPServer("COMSOL Editable Models", version="1.0.0", instructions="""
Create native editable COMSOL MPH models using the installed COMSOL Java API.
First call comsol_status, then get_template. All model paths are relative to the workspace.
Jobs run asynchronously and sequentially: poll job_status until a terminal state.
Always report failures and inspect logs. Never describe a queued job as a created model.
Use a new output filename for every edit. Java code runs with the local user's privileges;
only execute trusted modeling code. Physics types depend on installed COMSOL modules.
""")


@mcp.tool()
def comsol_status() -> dict:
    """Locate COMSOL and workspace. Discovery alone does not validate a license."""
    try:
        home = str(installation())
        error = None
    except RuntimeError as exc:
        home, error = None, str(exc)
    return {"installation": home, "workspace": str(ROOT), "error": error,
            "license": "Validated only when a batch job succeeds", "platform": "Windows"}


@mcp.tool()
def list_models() -> list[dict]:
    """List saved editable MPH files in the workspace."""
    return [{"file": str(p.relative_to(ROOT)), "bytes": p.stat().st_size}
            for p in ROOT.rglob("*.mph") if not p.is_relative_to(JOBS)]


@mcp.tool()
def get_template(name: str = "block") -> dict:
    """Return ready-to-run Java bodies: block, heat_transfer, inspect, export_java."""
    path = BASE / "examples" / (name + ".java.txt")
    if name not in {"block", "heat_transfer", "inspect", "export_java"}:
        raise ValueError("Choose block, heat_transfer, inspect, or export_java")
    return {"name": name, "java_body": path.read_text(encoding="utf-8")}


@mcp.tool()
def create_model(java_body: str, output_file: str, timeout_seconds: int = 600) -> dict:
    """Create a model from Java statements acting on `model`; return a job ID.

    Do not provide a class or main method. The wrapper saves the native MPH file.
    Full COMSOL API access supports geometry, selections, materials, physics, mesh,
    studies, solvers, plots and exports. This executes trusted local Java code.
    """
    return submit(java_body, output_file, None, timeout_seconds)


@mcp.tool()
def edit_model(input_file: str, output_file: str, java_body: str,
               timeout_seconds: int = 600) -> dict:
    """Load an existing MPH, apply Java API statements and save a new editable copy."""
    return submit(java_body, output_file, input_file, timeout_seconds)


@mcp.tool()
def set_parameters(input_file: str, output_file: str, parameters: dict[str, str],
                   rebuild_geometry: bool = True, study: str | None = None,
                   timeout_seconds: int = 600) -> dict:
    """Edit parameter expressions, optionally rebuild geometry and run a study.

    Existing solutions are not automatically recomputed unless study is provided.
    """
    body = "\n".join(f"model.param().set({java_string(k)}, {java_string(v)});" for k, v in parameters.items())
    if rebuild_geometry:
        body += '\nfor (String c : model.component().tags()) { for (String g : model.component(c).geom().tags()) { model.component(c).geom(g).run(); } }'
    if study:
        body += f'\nmodel.study({java_string(study)}).run();'
    return submit(body, output_file, input_file, timeout_seconds)


@mcp.tool()
def solve_model(input_file: str, output_file: str, study: str = "std1",
                timeout_seconds: int = 3600) -> dict:
    """Run an existing study and save its solution in a new editable MPH file."""
    return submit(f'model.study({java_string(study)}).run();', output_file, input_file, timeout_seconds)


@mcp.tool()
def job_status(job_id: str, tail_characters: int = 12000) -> dict:
    """Read job state and bounded log tails; terminal states include succeeded/failed/cancelled/interrupted."""
    directory = job_dir(job_id)
    if not 0 <= tail_characters <= 50000:
        raise ValueError("tail_characters must be 0..50000")
    with LOCK:
        state = json.loads((directory / "status.json").read_text())
    state["logs"] = {p.name: p.read_text(errors="replace")[-tail_characters:] if tail_characters else ""
                     for p in directory.glob("*.log")}
    state["artifacts"] = [p.name for p in directory.iterdir() if p.is_file()]
    return state


@mcp.tool()
def read_job_artifact(job_id: str, filename: str, offset: int = 0, limit: int = 16000) -> dict:
    """Read generated Java, text, CSV or logs (paged). Binary MPH files are returned as paths by job_status."""
    directory = job_dir(job_id)
    path = (directory / filename).resolve()
    if path.parent != directory or path.suffix.lower() not in {".java", ".txt", ".csv", ".log", ".json"}:
        raise ValueError("Expected a text artifact directly inside this job directory")
    if offset < 0 or not 1 <= limit <= 50000:
        raise ValueError("Invalid offset or limit")
    with path.open(encoding="utf-8", errors="replace") as stream:
        stream.read(offset)
        text = stream.read(limit)
        more = bool(stream.read(1))
    return {"text": text, "next_offset": offset + len(text), "has_more": more}


@mcp.tool()
def cancel_job(job_id: str) -> dict:
    """Cancel a queued/running job and terminate only its COMSOL process tree."""
    directory = job_dir(job_id)
    with LOCK:
        state = json.loads((directory / "status.json").read_text())
        if state["state"] not in {"queued", "compiling", "running"}:
            return state
        CANCELLED.add(job_id)
        process = ACTIVE.get(job_id)
    if process:
        kill(process)
    return update(directory, state="cancelled")


def shutdown() -> None:
    with LOCK:
        for status_file in JOBS.glob("*/status.json"):
            state = json.loads(status_file.read_text())
            if state.get("state") in {"queued", "compiling", "running"}:
                CANCELLED.add(state["id"])
                update(status_file.parent, state="cancelled", error="MCP server shutting down")
        processes = list(ACTIVE.items())
        CANCELLED.update(k for k, _ in processes)
        POOL.shutdown(wait=False, cancel_futures=True)
    for _, process in processes:
        kill(process)


if __name__ == "__main__":
    workspace_lock = acquire_workspace()
    try:
        mcp.run(transport="stdio")
    finally:
        shutdown()
        workspace_lock.close()
