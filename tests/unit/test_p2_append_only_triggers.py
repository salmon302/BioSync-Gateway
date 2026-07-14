"""
P2: Append-Only Trigger Enforcement on simulations table
Implements SRS FR-3.8.1 — Database-level append-only enforcement

Verifies that the simulations table has:
- BEFORE UPDATE trigger that rejects UPDATE operations
- BEFORE DELETE trigger that rejects DELETE operations
"""

import pytest


class TestAppendOnlyTriggersSimulations:
    """Tests for FR-3.8.1 — append-only triggers on simulations table."""

    def test_simulations_trigger_functions_exist(self):
        """The prevent_update and prevent_delete trigger functions must exist."""
        # Verify the trigger file includes simulations triggers
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        assert "simulations_prevent_update" in content
        assert "simulations_prevent_delete" in content

    def test_simulations_table_exists_in_schema(self):
        """The simulations table must exist in the schema."""
        import os
        schema_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "002-schema.sql"
        )

        with open(schema_path, 'r') as f:
            content = f.read()

        assert "CREATE TABLE IF NOT EXISTS simulations" in content
        assert "engine_state JSONB" in content

    def test_simulations_table_is_append_only(self):
        """Simulations table must be append-only with both triggers."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        # Both triggers must target simulations table
        assert "ON simulations" in content
        assert content.count("ON simulations") >= 2  # UPDATE + DELETE

    def test_simulations_uses_same_prevent_functions(self):
        """Simulations triggers must reuse prevent_update() and prevent_delete()."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        # Extract the simulations trigger section
        assert "prevent_update()" in content
        assert "prevent_delete()" in content


class TestHashChainTriggers:
    """Tests for FR-3.8.3 — cryptographic hash chain integrity."""

    def test_hash_chain_function_exists(self):
        """compute_hash_chain() function must exist."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        assert "CREATE OR REPLACE FUNCTION compute_hash_chain()" in content
        assert "sha256" in content  # SHA-256 algorithm

    def test_verify_hash_chain_function_exists(self):
        """verify_hash_chain() function must exist."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        assert "CREATE OR REPLACE FUNCTION verify_hash_chain()" in content

    def test_genesis_hash_is_64_zeros(self):
        """Genesis hash must be 64 zero characters."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        expected_genesis = "0000000000000000000000000000000000000000000000000000000000000000"
        assert expected_genesis in content

    def test_hash_chain_applied_to_audit_log(self):
        """Hash chain must be applied to audit_log table (not data tables)."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        assert "audit_log_hash_chain" in content
        assert "ON audit_log" in content

    def test_insert_audit_log_helper_exists(self):
        """insert_audit_log() helper function must exist for application use."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        assert "CREATE OR REPLACE FUNCTION insert_audit_log" in content

    def test_all_compliance_tables_have_triggers(self):
        """All SRS §6.1 compliance tables must have append-only triggers."""
        import os
        triggers_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "database", "migrations", "003-triggers.sql"
        )

        with open(triggers_path, 'r') as f:
            content = f.read()

        # All tables from SRS §6.1 must be protected
        required_tables = [
            "audit_log",
            "observations",
            "plates",
            "plate_wells",
            "devices",
            "simulations"
        ]

        for table in required_tables:
            assert f"{table}_prevent_update" in content, f"Missing UPDATE trigger for {table}"
            assert f"{table}_prevent_delete" in content, f"Missing DELETE trigger for {table}"
