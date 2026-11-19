"""Command-line interface for `comsol-mcp-unified`."""

from __future__ import annotations

import argparse
import json
import sys

from .catalog import build_catalog_from_install
from .compat import MCP_SDK_MAJOR, list_registered_resources, list_registered_tools
from .config import ALL_PROFILES, Settings
from .knowledge import RagKnowledgeBase
from .server import build_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="comsol-mcp",
        description="Unified, modular MCP server for COMSOL Multiphysics",
    )
    parser.add_argument(
        "--profiles",
        default=None,
        help=f"Comma-separated profiles to enable ({','.join(ALL_PROFILES)}, or 'all').",
    )
    parser.add_argument("--workspace", default=None, help="Workspace directory for models & batch jobs.")
    parser.add_argument("--dryrun", action="store_true", help="Start interactive tools in dry-run simulator mode.")

    sub = parser.add_subparsers(dest="command")
    sub.add_parser("serve", help="Run the stdio MCP server (default).")
    web_p = sub.add_parser("web", help="Run the lightweight local status dashboard.")
    web_p.add_argument("--port", type=int, default=None, help="HTTP port (default: COMSOL_MCP_WEB_PORT or 8765).")
    sub.add_parser("catalog-build", help="Extract offline API catalog JSONs from your local COMSOL installation XMLs.")
    rag_p = sub.add_parser("rag-build", help="Build or rebuild the local ChromaDB RAG index from your COMSOL PDFs.")
    rag_p.add_argument("--rebuild", action="store_true", help="Recreate the vector collection from scratch.")
    rag_p.add_argument("--max-files", type=int, default=None, help="Optional limit on PDF files to index.")
    sub.add_parser("doctor", help="Print detected COMSOL install, MCP SDK version, backends, and active tools.")

    args = parser.parse_args(argv)
    cmd = args.command or "serve"

    if cmd == "serve":
        bundle = build_server(
            profiles=args.profiles,
            workspace=args.workspace,
            dryrun=True if args.dryrun else None,
        )
        bundle.run_stdio()
        return 0

    settings = Settings.from_env(
        profiles=args.profiles,
        workspace=args.workspace,
        dryrun=True if args.dryrun else None,
    )

    if cmd == "doctor":
        bundle = build_server(settings=settings)
        report = {
            "mcp_sdk_major": MCP_SDK_MAJOR,
            "mounted_profiles": bundle.mounted_profiles,
            "tool_count": len(list_registered_tools(bundle.mcp)),
            "resource_count": len(list_registered_resources(bundle.mcp)),
            "status": bundle.hub.overall_status(),
            "catalog": bundle.catalog.info(),
            "rag": bundle.rag.status(),
        }
        print(json.dumps(report, indent=2))
        return 0

    if cmd == "catalog-build":
        if not settings.comsol_home:
            print("ERROR: COMSOL installation not found. Set COMSOL_HOME.", file=sys.stderr)
            return 1
        meta = build_catalog_from_install(settings.comsol_home, settings.catalog_dir)
        print(json.dumps(meta, indent=2))
        return 0

    if cmd == "rag-build":
        kb = RagKnowledgeBase(settings)
        result = kb.build(rebuild=args.rebuild, max_files=args.max_files)
        print(json.dumps(result, indent=2))
        return 0

    if cmd == "web":
        from .web.server import run_dashboard

        run_dashboard(settings=settings, port=args.port or settings.web_port)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
