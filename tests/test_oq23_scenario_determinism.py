# SPDX-License-Identifier: MIT
"""
OQ-23 - Scenario determinism (SRS FR-3.16.4).

Given the same scenario seed + configuration, the system shall reproduce
identical output hashes for all deterministic (non-LLM) modules across repeated
runs. The LLM module is recorded by provider/model for provenance (it is
non-deterministic by design) and is NOT hashed for equality.

DB-gated (runs in CI against postgres:15, consistent with the other v1.1
module tests). Offline: the default mock LLM provider requires no network.
"""
import os

import pytest

DATABASE_URL = os.getenv("DATABASE_URL")
requires_db = pytest.mark.skipif(
    not DATABASE_URL,
    reason="DATABASE_URL not set - requires a live PostgreSQL (CI provides it)",
)

ALL_FIVE = ["pk_pd", "chemistry", "digital_twin", "mrd", "llm"]
DETERMINISTIC = ["pk_pd", "chemistry", "digital_twin", "mrd"]


def _make_scenario(db, modules, seed):
    from uuid import uuid4

    from models import SimulationScenario

    row = SimulationScenario(
        scenario_uid=str(uuid4()),
        name="OQ-23 determinism",
        feature_modules=modules,
        seed=seed,
        config={},
        is_finalized=False,
    )
    db.add(row)
    db.flush()
    return row


def _run_once(db, scenario):
    from uuid import uuid4

    from models import ScenarioRun
    from simulation.scenarios import run_scenario

    run_row = ScenarioRun(
        run_uid=str(uuid4()),
        scenario_id=scenario.id,
        seed=scenario.seed,
        status="running",
    )
    db.add(run_row)
    db.flush()
    run_scenario(db, scenario, run_row)
    db.commit()
    db.refresh(run_row)
    return run_row


@requires_db
def test_oq23_deterministic_module_hashes_identical():
    """Same seed + config -> identical deterministic-module output hashes."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        seed = {"batch": 42, "site": "A"}
        scenario = _make_scenario(db, ALL_FIVE, seed)
        db.commit()
        db.refresh(scenario)

        r1 = _run_once(db, scenario)
        r2 = _run_once(db, scenario)

        h1 = r1.output_hashes
        h2 = r2.output_hashes
        assert set(h1.keys()) == set(ALL_FIVE)

        # Deterministic modules must reproduce identical hashes.
        for mod in DETERMINISTIC:
            assert h1[mod] == h2[mod], f"{mod} hash differs across runs"

        # LLM module records provider/model for provenance (not hashed equal).
        assert h1["llm"]["provider"] == h2["llm"]["provider"]
        assert h1["llm"]["model"] == h2["llm"]["model"]
        assert h1["llm"]["prompt_hash"] == h2["llm"]["prompt_hash"]

        # Same seed -> identical aggregated deterministic outputs (defense in depth).
        assert (
            r1.aggregated_outputs["pk_pd"]["target_matrix"]
            == r2.aggregated_outputs["pk_pd"]["target_matrix"]
        )
        assert (
            r1.aggregated_outputs["chemistry"]["chemistry_vectors"]
            == r2.aggregated_outputs["chemistry"]["chemistry_vectors"]
        )
    finally:
        db.close()


@requires_db
def test_oq23_different_seed_changes_hashes():
    """Different seed -> different deterministic-module output hashes."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        s_a = _make_scenario(db, ["pk_pd", "chemistry"], {"v": 1})
        s_b = _make_scenario(db, ["pk_pd", "chemistry"], {"v": 2})
        db.commit()
        db.refresh(s_a)
        db.refresh(s_b)

        r_a = _run_once(db, s_a)
        r_b = _run_once(db, s_b)

        assert r_a.output_hashes["pk_pd"] != r_b.output_hashes["pk_pd"]
        assert r_a.output_hashes["chemistry"] != r_b.output_hashes["chemistry"]
    finally:
        db.close()


@requires_db
def test_oq23_subset_modules_only_selected():
    """Only the modules in feature_modules are executed (FR-3.16.1 subset)."""
    from database import SessionLocal

    db = SessionLocal()
    try:
        scenario = _make_scenario(db, ["pk_pd", "mrd"], {"subset": 7})
        db.commit()
        db.refresh(scenario)
        r = _run_once(db, scenario)
        assert set(r.aggregated_outputs.keys()) == {"pk_pd", "mrd"}
        assert "chemistry" not in r.aggregated_outputs
    finally:
        db.close()
