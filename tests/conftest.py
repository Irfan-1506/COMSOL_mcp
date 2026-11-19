"""Shared pytest fixtures for comsol-mcp-unified."""

from __future__ import annotations

from pathlib import Path
import pytest

from comsol_mcp.config import Settings
from comsol_mcp.server import ServerBundle, build_server


@pytest.fixture
def tmp_settings(tmp_path: Path) -> Settings:
    ws = tmp_path / "models"
    ws.mkdir()
    return Settings(
        repo_root=Path(__file__).resolve().parents[1],
        workspace=ws,
        catalog_dir=tmp_path / "catalog_cache",
        pdf_dir=tmp_path / "pdf",
        knowledge_dir=tmp_path / "knowledge_base",
        comsol_home=None,
        cores=2,
        dryrun=True,
    )


@pytest.fixture
def dryrun_bundle(tmp_settings: Settings) -> ServerBundle:
    bundle = build_server(settings=tmp_settings)
    yield bundle
    bundle.hub.shutdown()
