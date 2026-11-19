"""Unified configuration, profile parsing, and COMSOL installation discovery."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

ALL_PROFILES: tuple[str, ...] = (
    "core",
    "physics",
    "batch",
    "gui",
    "catalog",
    "validate",
    "rag",
    "dryrun",
)


def _load_dotenv_file(path: Path) -> None:
    """Load simple KEY=VALUE lines from an optional .env / env.local file without extra deps."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def parse_profiles(raw: Optional[str]) -> tuple[str, ...]:
    """Parse a comma-separated profile list or 'all' into validated profile names."""
    if not raw or raw.strip().lower() == "all":
        return ALL_PROFILES
    items = [p.strip().lower() for p in raw.split(",") if p.strip()]
    if "all" in items:
        return ALL_PROFILES
    unknown = [p for p in items if p not in ALL_PROFILES]
    if unknown:
        raise ValueError(
            f"Unknown COMSOL_MCP_PROFILES: {unknown}. Valid profiles: {list(ALL_PROFILES)} or 'all'."
        )
    # Preserve order while deduplicating
    seen: list[str] = []
    for p in items:
        if p not in seen:
            seen.append(p)
    return tuple(seen)


def discover_comsol_home(configured: Optional[str] = None) -> Optional[Path]:
    """Locate a local COMSOL Multiphysics installation directory."""
    env_home = configured or os.environ.get("COMSOL_HOME")
    candidates: list[Path] = []
    if env_home:
        candidates.append(Path(env_home))

    system = platform.system()
    if system == "Windows":
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates.extend(sorted(pf.glob("COMSOL/COMSOL*/Multiphysics"), reverse=True))
    elif system == "Darwin":
        candidates.extend(sorted(Path("/Applications").glob("COMSOL*/Multiphysics"), reverse=True))
    else:
        for base in (Path("/usr/local"), Path("/opt")):
            candidates.extend(sorted(base.glob("comsol*/multiphysics"), reverse=True))
            candidates.extend(sorted(base.glob("COMSOL*/Multiphysics"), reverse=True))

    for home in candidates:
        if not home.is_dir():
            continue
        if (home / "bin" / "win64" / "comsolbatch.exe").is_file():
            return home.resolve()
        if (home / "bin" / "comsol").is_file() or (home / "bin" / "comsolbatch").is_file():
            return home.resolve()
    return None


def _default_repo_root() -> Path:
    # src/comsol_mcp/config.py -> repo root is 3 levels up
    return Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    """Runtime settings for the unified COMSOL MCP server."""

    repo_root: Path = field(default_factory=_default_repo_root)
    workspace: Path = field(default_factory=lambda: _default_repo_root() / "models")
    catalog_dir: Path = field(default_factory=lambda: _default_repo_root() / "catalog_cache")
    pdf_dir: Path = field(default_factory=lambda: _default_repo_root() / "pdf")
    knowledge_dir: Path = field(default_factory=lambda: _default_repo_root() / "knowledge_base")
    comsol_home: Optional[Path] = None
    cores: int = 2
    dryrun: bool = False
    profiles: tuple[str, ...] = ALL_PROFILES
    embedding_provider: str = "local"
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_api_key: str = ""
    embedding_endpoint: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings"
    embedding_dimension: int = 1024
    web_port: int = 8765

    @classmethod
    def from_env(
        cls,
        profiles: Optional[str] = None,
        workspace: Optional[str | Path] = None,
        dryrun: Optional[bool] = None,
    ) -> "Settings":
        root = _default_repo_root()
        _load_dotenv_file(root / ".env")
        _load_dotenv_file(root / "env.local")

        ws = Path(workspace) if workspace else Path(
            os.environ.get("COMSOL_MCP_WORKSPACE", str(root / "models"))
        )
        ws = ws.resolve()
        ws.mkdir(parents=True, exist_ok=True)

        cat = Path(os.environ.get("COMSOL_MCP_CATALOG_DIR", str(root / "catalog_cache"))).resolve()
        pdf = Path(os.environ.get("COMSOL_MCP_PDF_DIR", str(root / "pdf"))).resolve()
        kb = Path(os.environ.get("COMSOL_MCP_KNOWLEDGE_DIR", str(root / "knowledge_base"))).resolve()

        raw_profiles = profiles if profiles is not None else os.environ.get("COMSOL_MCP_PROFILES", "all")
        parsed_profiles = parse_profiles(raw_profiles)

        dry = (
            dryrun
            if dryrun is not None
            else os.environ.get("COMSOL_MCP_DRYRUN", "false").strip().lower() in {"1", "true", "yes", "on"}
        )

        cores = max(1, int(os.environ.get("COMSOL_MCP_CORES", "2")))
        web_port = int(os.environ.get("COMSOL_MCP_WEB_PORT", "8765"))

        api_key = os.environ.get("COMSOL_MCP_EMBEDDING_API_KEY") or os.environ.get("DASHSCOPE_API_KEY", "")
        provider = os.environ.get("COMSOL_MCP_EMBEDDING_PROVIDER", "local").strip().lower()

        return cls(
            repo_root=root,
            workspace=ws,
            catalog_dir=cat,
            pdf_dir=pdf,
            knowledge_dir=kb,
            comsol_home=discover_comsol_home(),
            cores=cores,
            dryrun=dry,
            profiles=parsed_profiles,
            embedding_provider=provider,
            embedding_model=os.environ.get("COMSOL_MCP_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            embedding_api_key=api_key,
            embedding_endpoint=os.environ.get(
                "COMSOL_MCP_EMBEDDING_ENDPOINT",
                "https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings",
            ),
            embedding_dimension=int(os.environ.get("COMSOL_MCP_EMBEDDING_DIMENSION", "1024")),
            web_port=web_port,
        )

    def comsol_binary(self, name: str) -> Optional[Path]:
        """Resolve a COMSOL CLI executable (e.g. 'comsolbatch', 'comsolcompile')."""
        home = self.comsol_home or discover_comsol_home()
        if not home:
            return None
        if platform.system() == "Windows":
            candidate = home / "bin" / "win64" / f"{name}.exe"
        else:
            candidate = home / "bin" / name
        return candidate if candidate.is_file() else None
