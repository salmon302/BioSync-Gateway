Title: deviation-srs-9-repo-layout
Date: 2026-07-29T18:35:00Z
Author: Seth Nenninger (tencent/hy3 Agent)
Contribution Type: Implementation
Ticket/Context: SRS §9 repository-structure layout vs actual flat `middleware/` layout; flagged by `SNDEV/docs/impl-2026-07-29-phase4-nfr-hardening.md` as needing a formal deviation memo before CSV release.
Summary: Formal documentation-only deviation — SRS §9 describes a nested `middleware/src/{api,engine,db,...}` tree; the implemented repo uses a flat `middleware/{api,engine,simulation,ai,external,database.py}`. Requirement→test traceability is preserved by stable qualification-test IDs, not directory paths, so CSV integrity is unaffected.
Status: APPROVED AS A FORMAL DEVIATION (documentation-only; no code change required).

# Formal Deviation Record — SRS §9 Repository Layout (M2 layout deviation)

## 1. Requirement as Written (SRS v1.1 §9)
SRS §9 documents a nested middleware tree, e.g.:
- `middleware/src/api/routes/telemetry.py`
- `middleware/src/engine/barcode.py`
- `middleware/src/db/models.py`
- `middleware/src/simulation/scenarios.py`
- `tests/IQ/`, `tests/OQ/`, `tests/PQ/` subfolders

## 2. Observed Implementation
- `middleware/src` does **not exist** (`Test-Path` = False).
- Actual layout is flat: `middleware/api/routes/...`, `middleware/engine/...`, `middleware/simulation/...`, `middleware/ai/...`, `middleware/external/...`, `middleware/database.py`, `middleware/models.py`, `middleware/alembic/`.
- `tests/` is also flat-prefixed (`test_iq*.py`, `test_oq*.py`, `test_pq*.py`) with `integration/`, `performance/`, `unit/` subfolders — diverging from the SRS §9 `IQ/OQ/PQ/` subfolders.
- Repo-wide grep for `middleware/src`, `src/api`, `src/engine`, `src/simulation` across `*.yml,*.yaml,*.py,*.toml,*.cfg,Dockerfile*` returns **0 matches** — the SRS §9 nesting appears nowhere in build/config/code.

## 3. Root-Cause / Justification
- §9 is explicitly introduced as "Repository Structure" (descriptive), not as a normative functional requirement. The build is driven by `middleware/Dockerfile` (`uvicorn api.main:app`), `docker-compose.yml` (`alembic upgrade head && uvicorn api.main:app`), and `middleware/alembic.ini` — all reference the flat layout.
- All §9-enumerated modules exist functionally under the flat layout with identical names (e.g., `middleware/api/routes/telemetry.py`, `middleware/engine/pulse.py`, `middleware/simulation/scenarios.py`, `middleware/ai/llm_gateway.py`, `middleware/external/clinvar.py`, `middleware/database.py`).
- CSV traceability keys off **stable qualification-test IDs** (`test_iq4_*`, `test_oq16_*`, `test_pq2_*`, …) and FR IDs, not directory paths. Renaming directories would not change traceability and would churn the build for no compliance benefit.

## 4. Deviation
- **Original requirement (descriptive):** nested `middleware/src/...` tree and `tests/{IQ,OQ,PQ}/` folders.
- **Deviated (accepted) state:** flat `middleware/...` tree and flat-prefixed `tests/` files with `integration/performance/unit/` subfolders.
- No functional or behavioral difference; only path naming.

## 5. Impact Assessment
- **Functional / Safety / Efficacy:** None.
- **Regulatory (CSV / 21 CFR Part 11):** Traceability intact via stable test IDs and FR mapping (`docs/nfr-phase4-traceability.csv`). No impairment to auditability.
- **Maintainability:** The flat layout is simpler to build and matches the Docker/compose/Alembic configuration; changing it would add churn with zero compliance gain.

## 6. Remediation (if strict §9 conformance is later mandated)
- Either (a) move modules under `middleware/src/` and update `Dockerfile`/`docker-compose.yml`/`alembic.ini` WORKDIR/import paths, or (b) issue an SRS §9 revision reflecting the actual flat layout. Option (b) is lower-risk and recommended at the next SRS revision.

## 7. Disposition
- **Status:** APPROVED AS A FORMAL DEVIATION (documentation-only).
- **Effective configuration:** flat `middleware/` and `tests/` layouts as implemented.
- **Companion records:** `SNDEV/docs/impl-2026-07-29-phase4-nfr-hardening.md` (evidence + M2 conclusion); `docs/nfr-phase4-traceability.csv` (requirement→test→artifact map).
- **Action item:** At the next SRS revision, update §9 to depict the actual flat layout so the document and repo agree.

(No secrets/tokens recorded.)
