"""Pluggable embedding providers for PDF RAG: local sentence-transformers OR OpenAI/DashScope API."""

from __future__ import annotations

import json
import urllib.request
from typing import Sequence

from ..config import Settings


class EmbeddingProvider:
    """Computes dense vectors using either local sentence-transformers or a compatible HTTP API."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._local_model = None

    @property
    def provider_name(self) -> str:
        return self.settings.embedding_provider

    def status(self) -> dict[str, object]:
        if self.provider_name == "api":
            return {
                "provider": "api",
                "model": self.settings.embedding_model,
                "endpoint": self.settings.embedding_endpoint,
                "api_key_configured": bool(self.settings.embedding_api_key),
                "ready": bool(self.settings.embedding_api_key),
            }
        try:
            import sentence_transformers  # type: ignore  # noqa: F401

            available = True
        except ModuleNotFoundError:
            available = False
        return {
            "provider": "local",
            "model": self.settings.embedding_model,
            "sentence_transformers_installed": available,
            "ready": available,
        }

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if self.provider_name == "api":
            return self._embed_api(texts)
        return self._embed_local(texts)

    def _embed_local(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Local embeddings require `sentence-transformers`. Install with `pip install comsol-mcp-unified[rag-local]` "
                "or set COMSOL_MCP_EMBEDDING_PROVIDER=api."
            ) from exc
        if self._local_model is None:
            self._local_model = SentenceTransformer(self.settings.embedding_model)
        vecs = self._local_model.encode(list(texts), normalize_embeddings=True)
        return [v.tolist() for v in vecs]

    def _embed_api(self, texts: Sequence[str]) -> list[list[float]]:
        if not self.settings.embedding_api_key:
            raise RuntimeError("COMSOL_MCP_EMBEDDING_API_KEY (or DASHSCOPE_API_KEY) is required when provider='api'.")
        results: list[list[float]] = []
        batch_size = 10
        for i in range(0, len(texts), batch_size):
            batch = list(texts[i : i + batch_size])
            payload = {
                "model": self.settings.embedding_model,
                "input": batch,
            }
            if self.settings.embedding_dimension:
                payload["dimensions"] = self.settings.embedding_dimension
            req = urllib.request.Request(
                self.settings.embedding_endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.settings.embedding_api_key}",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            rows = sorted(body["data"], key=lambda item: item["index"])
            results.extend(item["embedding"] for item in rows)
        return results
