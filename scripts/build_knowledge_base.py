"""CLI helper script: build ChromaDB RAG index from user-supplied local COMSOL PDFs."""

import sys

from comsol_mcp.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["rag-build", *sys.argv[1:]]))
