"""Minimal stdlib HTTP dashboard serving live status for backends, models, and batch jobs."""

from __future__ import annotations

import http.server
import json
import socketserver
from pathlib import Path
from typing import Any, Optional

from ..backends import BackendHub
from ..catalog import CatalogStore
from ..config import Settings
from ..knowledge import RagKnowledgeBase

WEB_DIR = Path(__file__).resolve().parent


def make_handler(hub: BackendHub, catalog: CatalogStore, rag: RagKnowledgeBase):
    class DashboardHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(WEB_DIR), **kwargs)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/api/status":
                payload = {
                    "status": hub.overall_status(),
                    "models": hub.batch.list_models(),
                    "recent_jobs": hub.batch.list_jobs(limit=15),
                    "catalog": catalog.info(),
                    "rag": rag.status(),
                }
                body = json.dumps(payload, indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            super().do_GET()

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            return

    return DashboardHandler


def run_dashboard(settings: Optional[Settings] = None, port: int = 8765) -> None:
    cfg = settings or Settings.from_env()
    hub = BackendHub(cfg)
    catalog = CatalogStore(cfg.catalog_dir)
    rag = RagKnowledgeBase(cfg)
    handler = make_handler(hub, catalog, rag)
    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        print(f"COMSOL Unified MCP dashboard running at http://127.0.0.1:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nDashboard stopped.")
