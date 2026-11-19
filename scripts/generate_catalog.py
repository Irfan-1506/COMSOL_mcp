"""CLI helper script: extract offline COMSOL API catalog from local installation XMLs."""

from comsol_mcp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["catalog-build"]))
