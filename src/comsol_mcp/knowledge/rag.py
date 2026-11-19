"""Optional local ChromaDB + PyMuPDF RAG knowledge base over user-supplied COMSOL PDFs."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..config import Settings
from .embeddings import EmbeddingProvider


def _chunk_text(text: str, chunk_chars: int = 1600, overlap: int = 200) -> list[str]:
    clean = " ".join(text.split())
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = min(len(clean), start + chunk_chars)
        chunks.append(clean[start:end])
        if end >= len(clean):
            break
        start = max(end - overlap, start + 1)
    return chunks


class RagKnowledgeBase:
    """Indexes local COMSOL PDFs into ChromaDB and runs semantic search."""

    COLLECTION_NAME = "comsol_docs"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embedder = EmbeddingProvider(settings)

    def _check_deps(self) -> list[str]:
        missing: list[str] = []
        for mod, pkg in (("pymupdf", "pymupdf"), ("chromadb", "chromadb")):
            try:
                __import__(mod)
            except ModuleNotFoundError:
                missing.append(pkg)
        return missing

    def status(self) -> dict[str, Any]:
        missing = self._check_deps()
        pdf_files = sorted(self.settings.pdf_dir.rglob("*.pdf")) if self.settings.pdf_dir.is_dir() else []
        indexed_chunks = 0
        if not missing and self.settings.knowledge_dir.is_dir():
            try:
                import chromadb  # type: ignore

                client = chromadb.PersistentClient(path=str(self.settings.knowledge_dir))
                col = client.get_or_create_collection(self.COLLECTION_NAME)
                indexed_chunks = col.count()
            except Exception:
                indexed_chunks = 0
        return {
            "missing_dependencies": missing,
            "install_hint": "pip install comsol-mcp-unified[rag-local]" if missing else None,
            "pdf_dir": str(self.settings.pdf_dir),
            "pdf_count": len(pdf_files),
            "knowledge_dir": str(self.settings.knowledge_dir),
            "indexed_chunks": indexed_chunks,
            "embedding": self.embedder.status(),
            "ready_to_search": (len(missing) == 0 and indexed_chunks > 0 and bool(self.embedder.status().get("ready"))),
        }

    def build(self, *, rebuild: bool = False, max_files: Optional[int] = None) -> dict[str, Any]:
        missing = self._check_deps()
        if missing:
            raise RuntimeError(f"Missing RAG dependencies: {missing}. Install with `pip install comsol-mcp-unified[rag-local]`.")
        if not self.settings.pdf_dir.is_dir():
            raise FileNotFoundError(
                f"PDF directory '{self.settings.pdf_dir}' does not exist. Place your licensed COMSOL PDFs there first."
            )
        pdf_files = sorted(self.settings.pdf_dir.rglob("*.pdf"))
        if max_files:
            pdf_files = pdf_files[:max_files]
        if not pdf_files:
            return {"ok": False, "message": f"No PDF files found in '{self.settings.pdf_dir}'."}

        import chromadb  # type: ignore
        import pymupdf  # type: ignore

        self.settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
        client = chromadb.PersistentClient(path=str(self.settings.knowledge_dir))
        if rebuild:
            try:
                client.delete_collection(self.COLLECTION_NAME)
            except Exception:
                pass
        col = client.get_or_create_collection(self.COLLECTION_NAME)

        total_chunks = 0
        for pdf_path in pdf_files:
            rel = str(pdf_path.relative_to(self.settings.pdf_dir)).replace("\\", "/")
            module = pdf_path.parent.name if pdf_path.parent != self.settings.pdf_dir else "general"
            doc = pymupdf.open(str(pdf_path))
            ids: list[str] = []
            docs: list[str] = []
            metas: list[dict[str, Any]] = []
            for page_idx, page in enumerate(doc, start=1):
                text = page.get_text("text")
                for c_idx, chunk in enumerate(_chunk_text(text)):
                    ids.append(f"{rel}::p{page_idx}::c{c_idx}")
                    docs.append(chunk)
                    metas.append({"source": rel, "module": module, "page": page_idx})
            doc.close()
            if docs:
                vecs = self.embedder.embed(docs)
                col.upsert(ids=ids, documents=docs, embeddings=vecs, metadatas=metas)
                total_chunks += len(docs)

        return {"ok": True, "files_processed": len(pdf_files), "chunks_indexed": total_chunks, "collection_count": col.count()}

    def search(self, query: str, *, top_k: int = 5, module: Optional[str] = None) -> dict[str, Any]:
        missing = self._check_deps()
        if missing:
            raise RuntimeError(f"Missing RAG dependencies: {missing}. Install with `pip install comsol-mcp-unified[rag-local]`.")
        import chromadb  # type: ignore

        client = chromadb.PersistentClient(path=str(self.settings.knowledge_dir))
        col = client.get_or_create_collection(self.COLLECTION_NAME)
        if col.count() == 0:
            return {"query": query, "results": [], "note": "Knowledge base is empty. Run `rag_build` after placing PDFs in pdf/."}
        qvec = self.embedder.embed([query])[0]
        where = {"module": module} if module else None
        raw = col.query(query_embeddings=[qvec], n_results=max(1, min(top_k, 20)), where=where)
        results: list[dict[str, Any]] = []
        docs = (raw.get("documents") or [[]])[0]
        metas = (raw.get("metadatas") or [[]])[0]
        dists = (raw.get("distances") or [[]])[0]
        for doc, meta, dist in zip(docs, metas, dists):
            results.append({"text": doc, "metadata": meta, "distance": round(float(dist), 4)})
        return {"query": query, "count": len(results), "results": results}
