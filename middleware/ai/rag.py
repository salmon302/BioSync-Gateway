# SPDX-License-Identifier: MIT
"""
Local static RAG retrieval repository (FR-3.15.3 / C9).

Maintains a directory of markdown/JSON templates (CAP/CLIA reporting
templates, FDA device-manual text, Epic EHR documentation rubrics) used as
the RAG context source for LLM synthesis. Retrieval is a dependency-free
keyword / section-overlap scorer - sufficient for a *static* template corpus
(C9) and fully offline.

Also exposes :func:`seed_rag_templates` to register the on-disk corpus into the
append-only ``rag_templates`` registry table (FR-3.15.3).
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

RAG_TEMPLATE_DIR: str = os.getenv("RAG_TEMPLATE_DIR") or os.path.join(
    os.path.dirname(__file__), "rag_templates"
)

# Recognised template types (mirrors RagTemplate.template_type column).
TYPE_CAP_CLIA = "cap_clia"
TYPE_FDA_MANUAL = "fda_device_manual"
TYPE_EHR_RUBRIC = "ehr_rubric"
TYPE_PATHOLOGY = "pathology"

_STOPWORDS = set(
    "the a an and or of to in for with on at by from as is are be this that "
    "patient specimen test results indicates indicated suggest suggested "
    "using used use report note clinical summary section".split()
)


class RagTemplate:
    """A single RAG template loaded from disk."""

    def __init__(
        self,
        template_id: str,
        name: str,
        template_type: str,
        source_path: str,
        content: str,
        description: str = "",
    ):
        self.template_id = template_id
        self.name = name
        self.template_type = template_type
        self.source_path = source_path
        self.content = content
        self.description = description

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "name": self.name,
            "template_type": self.template_type,
            "source_path": self.source_path,
            "description": self.description,
            "content_chars": len(self.content),
        }


def _tokenize(text: str) -> List[str]:
    return [
        t
        for t in re.findall(r"[a-z0-9][a-z0-9+_.-]*", text.lower())
        if t not in _STOPWORDS and len(t) > 2
    ]


class RAGTemplateRepo:
    """Loads and retrieves from a static on-disk RAG template corpus."""

    def __init__(self, template_dir: str = RAG_TEMPLATE_DIR):
        self.template_dir = template_dir
        self.templates: List[RagTemplate] = []
        self._index: Dict[str, Dict[str, int]] = {}
        self.load()

    # -- loading ------------------------------------------------------------
    def load(self) -> int:
        """(Re)load all templates from ``template_dir``. Returns count."""
        self.templates = []
        self._index = {}
        if not os.path.isdir(self.template_dir):
            logger.warning("RAG template dir not found: %s", self.template_dir)
            return 0
        count = 0
        for fname in sorted(os.listdir(self.template_dir)):
            if fname.startswith(".") or fname.startswith("_"):
                continue
            path = os.path.join(self.template_dir, fname)
            if not os.path.isfile(path):
                continue
            if fname.lower().endswith((".md", ".markdown", ".json")):
                try:
                    tpl = self._parse_file(path)
                except Exception as exc:  # pragma: no cover
                    logger.error("Failed to parse RAG template %s: %s", path, exc)
                    continue
                if tpl:
                    self.templates.append(tpl)
                    count += 1
        self._build_index()
        logger.info("Loaded %d RAG templates from %s", count, self.template_dir)
        return count

    def _parse_file(self, path: str) -> Optional[RagTemplate]:
        name = os.path.basename(path)
        template_id = os.path.splitext(name)[0]
        template_type = TYPE_PATHOLOGY
        description = ""
        content = ""

        if path.lower().endswith(".json"):
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                template_id = data.get("template_id", template_id)
                template_type = data.get("template_type", template_type)
                description = data.get("description", "")
                content = data.get("content") or data.get("text") or json.dumps(data, indent=2)
        else:
            with open(path, "r", encoding="utf-8") as fh:
                raw = fh.read()
            # Optional YAML-ish frontmatter between the first two '---' lines.
            m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
            if m:
                try:
                    meta = json.loads(m.group(1))
                except Exception:
                    meta = {}
                template_id = meta.get("template_id", template_id)
                template_type = meta.get("template_type", template_type)
                description = meta.get("description", "")
                content = m.group(2)
            else:
                content = raw
            # Infer type from filename when not explicitly set.
            low = name.lower()
            if template_type == TYPE_PATHOLOGY:
                if "cap" in low or "clia" in low:
                    template_type = TYPE_CAP_CLIA
                elif "ehr" in low or "rubric" in low:
                    template_type = TYPE_EHR_RUBRIC
                elif "fda" in low:
                    template_type = TYPE_FDA_MANUAL

        if not description:
            heading = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
            description = heading.group(1).strip() if heading else template_id
        return RagTemplate(template_id, name, template_type, path, content, description)

    def _build_index(self) -> None:
        for tpl in self.templates:
            freq: Dict[str, int] = {}
            for tok in _tokenize(tpl.name + " " + tpl.description + " " + tpl.content):
                freq[tok] = freq.get(tok, 0) + 1
            self._index[tpl.template_id] = freq

    # -- retrieval ----------------------------------------------------------
    def retrieve(
        self,
        query: str,
        template_type: Optional[str] = None,
        top_k: int = 3,
    ) -> List[RagTemplate]:
        """Return the ``top_k`` templates most relevant to ``query``."""
        q_set = set(_tokenize(query))
        scored: List[Any] = []
        for tpl in self.templates:
            if template_type and tpl.template_type != template_type:
                continue
            freq = self._index.get(tpl.template_id, {})
            score = sum(freq.get(t, 0) for t in q_set)
            if q_set & set(_tokenize(tpl.name)):
                score += 2
            if score > 0:
                scored.append((score, tpl))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [t for _, t in scored[:top_k]]

    def get_by_id(self, template_id: str) -> Optional[RagTemplate]:
        for tpl in self.templates:
            if tpl.template_id == template_id:
                return tpl
        return None

    def as_context(self, templates: List[RagTemplate]) -> str:
        """Concatenate retrieved templates into a prompt context block."""
        blocks = [
            f"### TEMPLATE [{t.template_type}] {t.name}\n{t.content.strip()}"
            for t in templates
        ]
        return "\n\n".join(blocks)

    def registry_rows(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.templates]


# Module-level singleton (lazily initialized; cheap).
_repo: Optional[RAGTemplateRepo] = None


def get_rag_repo() -> RAGTemplateRepo:
    """Return the process-wide RAG repository singleton."""
    global _repo
    if _repo is None:
        _repo = RAGTemplateRepo()
    return _repo


def seed_rag_templates(db, repo: Optional[RAGTemplateRepo] = None) -> int:
    """
    Idempotently register on-disk RAG templates into the ``rag_templates``
    registry table (FR-3.15.3). Inserts missing rows only - the table is
    append-only / read-only after bulk load, so existing rows are left
    untouched (no UPDATE/DELETE, which the triggers would reject).

    Returns the number of rows ensured (present after the call).
    """
    from models import RagTemplate as RagTemplateModel

    repo = repo or get_rag_repo()
    ensured = 0
    for tpl in repo.templates:
        existing = (
            db.query(RagTemplateModel)
            .filter(RagTemplateModel.template_id == tpl.template_id)
            .first()
        )
        if existing is None:
            row = RagTemplateModel(
                template_id=tpl.template_id,
                template_name=tpl.name,
                template_type=tpl.template_type,
                source_path=tpl.source_path,
                description=tpl.description,
            )
            db.add(row)
        # Idempotent: if a row already exists, leave it as-is (append-only).
        ensured += 1
    db.flush()
    return ensured
