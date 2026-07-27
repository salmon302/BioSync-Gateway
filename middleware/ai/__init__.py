# SPDX-License-Identifier: MIT
"""AI / LLM-RAG gateway package (SRS FR-3.15)."""
from ai.llm_gateway import (
    generate_text,
    generate_text_async,
    get_provider_config,
    persist_run,
)
from ai.rag import (
    RAGTemplateRepo,
    RagTemplate,
    get_rag_repo,
    seed_rag_templates,
)

__all__ = [
    "generate_text",
    "generate_text_async",
    "get_provider_config",
    "persist_run",
    "RAGTemplateRepo",
    "RagTemplate",
    "get_rag_repo",
    "seed_rag_templates",
]
