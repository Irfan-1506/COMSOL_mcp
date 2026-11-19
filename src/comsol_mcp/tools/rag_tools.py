"""Embedded modeling guides, troubleshooting, and optional PDF RAG profile (`rag`)."""

from __future__ import annotations

from typing import Any, Optional

from ..knowledge import RagKnowledgeBase, get_doc, list_docs, troubleshoot as run_troubleshoot


def register_rag_tools(mcp: Any, rag: RagKnowledgeBase) -> None:
    @mcp.tool()
    def docs_get(topic: str = "list") -> dict[str, Any]:
        """Fetch built-in offline COMSOL guides (`workflow`, `mph_vs_batch`, `bc_properties`, `electrochemistry`, `best_practices`, or `list`)."""
        if topic.strip().lower() in {"list", "all", ""}:
            return {"topics": list_docs()}
        return get_doc(topic)

    @mcp.tool()
    def troubleshoot(symptom: str) -> dict[str, Any]:
        """Diagnose common COMSOL, MPh, JPype, solver convergence, and Windows batch errors."""
        return run_troubleshoot(symptom)

    @mcp.tool()
    def rag_status() -> dict[str, Any]:
        """Check local PDF directory, ChromaDB vector index count, and embedding provider readiness."""
        return rag.status()

    @mcp.tool()
    def rag_build(rebuild: bool = False, max_files: Optional[int] = None) -> dict[str, Any]:
        """Index user-supplied COMSOL PDF manuals from `COMSOL_MCP_PDF_DIR` into local ChromaDB."""
        return rag.build(rebuild=rebuild, max_files=max_files)

    @mcp.tool()
    def rag_search(query: str, top_k: int = 5, module: Optional[str] = None) -> dict[str, Any]:
        """Semantic search across the locally indexed COMSOL PDF knowledge base."""
        return rag.search(query=query, top_k=top_k, module=module)
