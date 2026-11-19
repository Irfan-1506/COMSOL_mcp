"""Optional Windows COMSOL Desktop GUI backend (window inspection, screenshots, Java Shell, sync)."""

from __future__ import annotations

import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Optional

from ..config import Settings

try:
    import psutil  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    psutil = None

try:
    import pyperclip  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    pyperclip = None

try:
    from PIL import ImageGrab  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    ImageGrab = None

try:
    from pywinauto import Desktop, keyboard  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    Desktop = None
    keyboard = None


_SAFE_MODEL_STMT_RE = re.compile(r"^\s*(?:model\.[A-Za-z0-9_.\(\)\[\]\"',+\-*/\s:=;]+|//.*)?\s*$")


class GuiBackend:
    """Windows COMSOL Desktop automation & Java Shell helper with graceful degradation."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.screenshots_dir = settings.workspace / "_gui_captures"

    def missing_dependencies(self) -> list[str]:
        missing: list[str] = []
        if platform.system() != "Windows":
            missing.append("Windows OS required")
            return missing
        if Desktop is None:
            missing.append("pywinauto")
        if pyperclip is None:
            missing.append("pyperclip")
        if ImageGrab is None:
            missing.append("Pillow")
        if psutil is None:
            missing.append("psutil")
        return missing

    def _find_comsol_windows(self) -> list[Any]:
        if Desktop is None or platform.system() != "Windows":
            return []
        try:
            desktop = Desktop(backend="uia")
            return [w for w in desktop.windows() if "COMSOL Multiphysics" in (w.window_text() or "")]
        except Exception:
            return []

    def _find_comsol_processes(self) -> list[dict[str, Any]]:
        if psutil is None:
            return []
        found: list[dict[str, Any]] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if "comsol" in name:
                    found.append({"pid": proc.info["pid"], "name": proc.info["name"]})
            except Exception:
                continue
        return found

    def status(self) -> dict[str, Any]:
        missing = self.missing_dependencies()
        windows = self._find_comsol_windows()
        return {
            "backend": "gui",
            "platform": platform.system(),
            "ready": len(missing) == 0,
            "missing_dependencies": missing,
            "install_hint": "pip install comsol-mcp-unified[gui]" if missing else None,
            "comsol_processes": self._find_comsol_processes(),
            "desktop_windows": [w.window_text() for w in windows],
            "desktop_running": len(windows) > 0,
        }

    def diagnose(self) -> dict[str, Any]:
        info = self.status()
        comsol_exe = self.settings.comsol_binary("comsol")
        info["comsol_desktop_exe"] = str(comsol_exe) if comsol_exe else None
        info["server_exe"] = str(self.settings.comsol_binary("comsolmphserver") or "") or None
        return info

    def open_model(self, model_path: Optional[str] = None, launch_server_port: Optional[int] = None) -> dict[str, Any]:
        if platform.system() != "Windows":
            raise RuntimeError("COMSOL Desktop GUI automation is only supported on Windows.")
        exe = self.settings.comsol_binary("comsol")
        if not exe:
            raise RuntimeError("comsol.exe not found. Set COMSOL_HOME to your Multiphysics directory.")
        cmd = [str(exe)]
        if launch_server_port:
            cmd.extend(["-port", str(launch_server_port)])
        if model_path:
            p = Path(model_path).resolve()
            if not p.is_file():
                raise FileNotFoundError(f"Model file not found: {p}")
            cmd.append(str(p))
        proc = subprocess.Popen(cmd)
        return {"ok": True, "pid": proc.pid, "command": cmd}

    def capture_window(self, output_path: Optional[str] = None, region: str = "full") -> dict[str, Any]:
        missing = self.missing_dependencies()
        if missing:
            raise RuntimeError(f"GUI capture unavailable; missing: {missing}. Install with `pip install comsol-mcp-unified[gui]`.")
        windows = self._find_comsol_windows()
        if not windows:
            raise RuntimeError("No open COMSOL Multiphysics Desktop window found.")
        win = windows[0]
        rect = win.rectangle()
        bbox = (rect.left, rect.top, rect.right, rect.bottom)
        if region == "graphics":
            # Graphics viewport typically occupies the right ~55% of the COMSOL Desktop frame
            w = rect.right - rect.left
            h = rect.bottom - rect.top
            bbox = (rect.left + int(w * 0.42), rect.top + int(h * 0.12), rect.right - 12, rect.bottom - int(h * 0.12))
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        target = Path(output_path) if output_path else self.screenshots_dir / f"comsol_{region}_{int(time.time())}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        img = ImageGrab.grab(bbox=bbox)
        img.save(str(target))
        return {"ok": True, "path": str(target.resolve()), "region": region, "bbox": list(bbox)}

    def validate_java_shell_code(self, code: str, allow_non_model_code: bool = False) -> None:
        if allow_non_model_code:
            return
        for idx, line in enumerate(code.splitlines(), start=1):
            if not _SAFE_MODEL_STMT_RE.match(line):
                raise ValueError(
                    f"Line {idx} rejected by Java Shell safety policy (only `model.` statements allowed by default): {line!r}. "
                    "Pass allow_non_model_code=True explicitly to override."
                )

    def execute_java_shell(self, code: str, *, allow_non_model_code: bool = False) -> dict[str, Any]:
        self.validate_java_shell_code(code, allow_non_model_code=allow_non_model_code)
        missing = self.missing_dependencies()
        if missing:
            raise RuntimeError(f"Java Shell automation unavailable; missing: {missing}.")
        windows = self._find_comsol_windows()
        if not windows:
            raise RuntimeError("No open COMSOL Multiphysics Desktop window found.")
        win = windows[0]
        win.set_focus()
        time.sleep(0.2)
        pyperclip.copy(code.strip())
        keyboard.send_keys("^v{ENTER}")
        return {"ok": True, "sent_lines": len(code.strip().splitlines()), "window": win.window_text()}
