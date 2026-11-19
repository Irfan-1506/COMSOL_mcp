"""Backend hub coordinating warm mph, dry-run simulator, native batch queue, and Desktop GUI."""

from __future__ import annotations

import threading
import time
from collections import Counter, deque
from typing import Any, Optional

from ..config import Settings
from .batch_backend import BatchJobBackend
from .dryrun_backend import DryRunBackend
from .gui_backend import GuiBackend
from .mph_backend import MPhBackend


class BackendHub:
    """Central runtime state container shared across all loaded MCP tool profiles."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mph = MPhBackend(settings.workspace)
        self.dryrun = DryRunBackend(settings.workspace)
        self.batch = BatchJobBackend(settings)
        self.gui = GuiBackend(settings)
        self.use_dryrun: bool = bool(settings.dryrun)

        self._stats_lock = threading.Lock()
        self._call_counts: Counter[str] = Counter()
        self._recent_calls: deque[dict[str, Any]] = deque(maxlen=100)

    @property
    def interactive(self) -> DryRunBackend | MPhBackend:
        """Return the currently active interactive modeling backend (dryrun or mph)."""
        return self.dryrun if self.use_dryrun else self.mph

    @property
    def interactive_name(self) -> str:
        return "dryrun" if self.use_dryrun else "mph"

    def set_dryrun(self, enabled: bool) -> dict[str, Any]:
        self.use_dryrun = bool(enabled)
        return {"ok": True, "interactive_backend": self.interactive_name}

    def record_call(self, tool_name: str, ok: bool, duration_ms: float, error: Optional[str] = None) -> None:
        with self._stats_lock:
            self._call_counts[tool_name] += 1
            self._recent_calls.append(
                {
                    "ts": round(time.time(), 3),
                    "tool": tool_name,
                    "ok": ok,
                    "duration_ms": round(duration_ms, 2),
                    "error": error,
                }
            )

    def call_stats(self) -> dict[str, Any]:
        with self._stats_lock:
            return {
                "total_calls": sum(self._call_counts.values()),
                "by_tool": dict(self._call_counts.most_common()),
                "recent": list(self._recent_calls)[-15:],
            }

    def overall_status(self) -> dict[str, Any]:
        return {
            "interactive_backend": self.interactive_name,
            "profiles": list(self.settings.profiles),
            "workspace": str(self.settings.workspace),
            "comsol_home": str(self.settings.comsol_home) if self.settings.comsol_home else None,
            "mph": self.mph.status(),
            "dryrun": self.dryrun.status(),
            "batch": self.batch.status(),
            "gui": self.gui.status(),
        }

    def shutdown(self) -> None:
        self.batch.shutdown()


__all__ = ["BackendHub", "BatchJobBackend", "DryRunBackend", "GuiBackend", "MPhBackend"]
