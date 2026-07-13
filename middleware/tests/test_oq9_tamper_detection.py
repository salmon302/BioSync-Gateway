"""
OQ-9: Tamper Detection Test
Verifies that hash chain detects tampering with audit log data.

Test Criteria:
- Alter JSONB in audit_log → verification reports broken row
- Hash chain verification identifies exact broken row
- Tamper detection works for both data and hash modification

SRS Reference: FR-3.8.3
"""

import pytest
from sqlalchemy import text
from datetime import datetime
import json


class TestOQ9TamperDetection:
    """
    Test suite for OQ-9: Tamper detection via hash chain
    """
    
    def test_tamper_detection_data_modification(self, db_session):
        """
        OQ-9 Test Case 1: Modify audit_log data → chain broken
        """
        # Insert a valid audit entry
        insert_query = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 1, '{"original": "data"}')
            RETURNING id, current_hash
        """)
        
        result = db_session.execute(insert_query)
        row = result.first()
        original_id = row[0]
        original_hash = row[1]
        db_session.commit()
        
        # Tamper: Modify the data directly in database
        tamper_query = text(f"""
            UPDATE audit_log 
            SET data = '{{"tampered": "data"}}'
            WHERE id = {original_id}
        """)
        
        # Disable trigger temporarily to simulate tampering
        db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update"))
        db_session.execute(tamper_query)
        db_session.commit()
        db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_prevent_update"))
        
        # Run hash chain verification
        verify_query = text("SELECT * FROM verify_hash_chain()")
        result = db_session.execute(verify_query).first()
        
        integrity_status = result[0]
        broken_at_id = result[1]
        
        # Verify tamper was detected
        assert integrity_status == "broken", \
            f"Tamper not detected. Status: {integrity_status}"
        assert broken_at_id == original_id, \
            f"Wrong broken row reported. Expected {original_id}, got {broken_at_id}"
    
    def test_tamper_detection_hash_modification(self, db_session):
        """
        OQ-9 Test Case 2: Modify current_hash → chain broken
        """
        # Insert valid audit entry
        insert_query = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 2, '{"test": "hash"}')
            RETURNING id
        """)
        
        result = db_session.execute(insert_query)
        record_id = result.scalar()
        db_session.commit()
        
        # Tamper: Modify the hash directly
        tamper_query = text(f"""
            UPDATE audit_log 
            SET current_hash = '0000000000000000000000000000000000000000000000000000000000000000'
            WHERE id = {record_id}
        """)
        
        db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update"))
        db_session.execute(tamper_query)
        db_session.commit()
        db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_prevent_update"))
        
        # Verify chain
        result = db_session.execute(text("SELECT * FROM verify_hash_chain()")).first()
        
        assert result[0] == "broken", "Hash modification not detected"
        assert result[1] == record_id, "Wrong broken row reported"
    
    def test_tamper_detection_prev_hash_modification(self, db_session):
        """
        OQ-9 Test Case 3: Modify previous_hash → chain broken
        """
        # Insert two entries to create chain
        insert1 = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 3, '{"entry": "1"}')
            RETURNING id
        """)
        result1 = db_session.execute(insert1)
        id1 = result1.scalar()
        
        insert2 = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 4, '{"entry": "2"}')
            RETURNING id
        """)
        result2 = db_session.execute(insert2)
        id2 = result2.scalar()
        db_session.commit()
        
        # Tamper: Modify previous_hash of second entry
        tamper_query = text(f"""
            UPDATE audit_log 
            SET previous_hash = 'ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff'
            WHERE id = {id2}
        """)
        
        db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update"))
        db_session.execute(tamper_query)
        db_session.commit()
        db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_prevent_update"))
        
        # Verify chain
        result = db_session.execute(text("SELECT * FROM verify_hash_chain()")).first()
        
        assert result[0] == "broken", "Previous hash tamper not detected"
        assert result[1] == id2, "Wrong broken row reported"
    
    def test_valid_chain_passes_verification(self, db_session):
        """
        OQ-9 Test Case 4: Valid chain should pass verification
        """
        # Insert multiple valid entries
        for i in range(5):
            insert_query = text(f"""
                INSERT INTO audit_log (table_name, operation, record_id, data)
                VALUES ('test_table', 'INSERT', {i+10}, '{{"entry": "{i}"}}')
            """)
            db_session.execute(insert_query)
        db_session.commit()
        
        # Verify chain
        result = db_session.execute(text("SELECT * FROM verify_hash_chain()")).first()
        
        assert result[0] == "ok", f"Valid chain marked as broken: {result}"
        assert result[1] is None, "Broken row reported for valid chain"
    
    def test_api_verify_endpoint(self, client, db_session):
        """
        OQ-9 Test Case 5: Test GET /api/audit/verify endpoint
        """
        # Insert valid entry
        insert_query = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 99, '{"api": "test"}')
        """)
        db_session.execute(insert_query)
        db_session.commit()
        
        # Call API endpoint
        response = client.get("/api/audit/verify")
        
        assert response.status_code == 200
        data = response.json()
        assert data["integrity"] == "ok", f"API verification failed: {data}"
        assert data["broken_at_row_id"] is None
    
    def test_api_detects_tampering(self, client, db_session):
        """
        OQ-9 Test Case 6: API endpoint detects tampering
        """
        # Insert entry
        insert_query = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 100, '{"tamper": "test"}')
            RETURNING id
        """)
        result = db_session.execute(insert_query)
        record_id = result.scalar()
        db_session.commit()
        
        # Tamper
        db_session.execute(text("ALTER TABLE audit_log DISABLE TRIGGER audit_log_prevent_update"))
        db_session.execute(text(f"""
            UPDATE audit_log SET data = '{{"tampered": true}}' WHERE id = {record_id}
        """))
        db_session.commit()
        db_session.execute(text("ALTER TABLE audit_log ENABLE TRIGGER audit_log_prevent_update"))
        
        # Call API
        response = client.get("/api/audit/verify")
        
        assert response.status_code == 200
        data = response.json()
        assert data["integrity"] == "broken", "Tampering not detected via API"
        assert data["broken_at_row_id"] == record_id


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
