# SPDX-License-Identifier: MIT
"""
Seed RAG templates into the rag_templates registry table (FR-3.15.3).

Idempotent: inserts missing template rows only. The rag_templates table is
append-only / read-only after bulk load, so re-running the seed is safe and
never issues UPDATE/DELETE.

Usage:
    python middleware/scripts/seed_rag_templates.py
"""
from __future__ import annotations

import logging
import os
import sys

# Ensure 'middleware' is importable when run directly.
_MW = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _MW not in sys.path:
    sys.path.insert(0, _MW)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("seed_rag_templates")


def main() -> int:
    from database import SessionLocal
    from ai.rag import get_rag_repo, seed_rag_templates

    db = SessionLocal()
    try:
        repo = get_rag_repo()
        n = seed_rag_templates(db, repo)
        db.commit()
        logger.info("Seeded %d RAG template registry rows.", n)
        return 0
    except Exception as exc:  # pragma: no cover
        db.rollback()
        logger.error("RAG template seed failed: %s", exc)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
