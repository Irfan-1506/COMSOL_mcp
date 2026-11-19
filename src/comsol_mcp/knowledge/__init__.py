"""Embedded COMSOL modeling guides, troubleshooting recipes, and RAG retrieval."""

from .embedded import DOC_TOPICS, get_doc, list_docs, troubleshoot
from .rag import RagKnowledgeBase

__all__ = ["DOC_TOPICS", "RagKnowledgeBase", "get_doc", "list_docs", "troubleshoot"]
