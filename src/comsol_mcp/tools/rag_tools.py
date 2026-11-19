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

    # --- Knowledge & PDF search parity tools (6) ---
    @mcp.tool()
    def docs_list() -> dict[str, Any]:
        """List all built-in offline COMSOL guide topics."""
        return {"topics": list_docs()}

    @mcp.tool()
    def physics_get_guide(topic: str = "bc_properties") -> dict[str, Any]:
        """Retrieve quick-reference physics & boundary condition property guides."""
        return get_doc(topic if topic in list_docs() else "bc_properties")

    @mcp.tool()
    def modeling_best_practices() -> dict[str, Any]:
        """Return COMSOL modeling, units, mesh convergence, and safety best practices."""
        return get_doc("best_practices")

    @mcp.tool()
    def pdf_search(query: str, top_k: int = 5, module: Optional[str] = None) -> dict[str, Any]:
        """Semantic vector search over locally indexed COMSOL PDF manuals."""
        return rag.search(query=query, top_k=top_k, module=module)

    @mcp.tool()
    def pdf_search_status() -> dict[str, Any]:
        """Check PDF vector search readiness, PDF count, and indexed chunk count."""
        return rag.status()

    @mcp.tool()
    def pdf_list_modules() -> dict[str, Any]:
        """List module subdirectories detected under `COMSOL_MCP_PDF_DIR`."""
        pdf_dir = rag.settings.pdf_dir
        if not pdf_dir.is_dir():
            return {"pdf_dir": str(pdf_dir), "modules": []}
        modules = sorted({p.parent.name for p in pdf_dir.rglob("*.pdf") if p.parent != pdf_dir})
        return {"pdf_dir": str(pdf_dir), "modules": modules}
