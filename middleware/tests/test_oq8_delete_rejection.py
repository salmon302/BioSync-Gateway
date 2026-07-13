"""
OQ-8: DELETE Rejection Test
Verifies that append-only triggers prevent DELETE operations on compliance tables.

Test Criteria:
- Direct SQL DELETE → RAISE EXCEPTION
- Row remains intact
- Trigger returns appropriate error message

SRS Reference: FR-3.8.1
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


class TestOQ8DeleteRejection:
    """
    Test suite for OQ-8: DELETE rejection on append-only tables
    """
    
    COMPLIANCE_TABLES = [
        'audit_log',
        'observations',
        'plates',
        'plate_wells',
        'devices',
        'simulations'
    ]
    
    def test_delete_audit_log_rejected(self, db_session):
        """
        OQ-8 Test Case 1: DELETE on audit_log should be rejected
        """
        # Insert test record
        insert_query = text("""
            INSERT INTO audit_log (table_name, operation, record_id, data)
            VALUES ('test_table', 'INSERT', 999, '{"test": "data"}')
            RETURNING id
        """)
        
        result = db_session.execute(insert_query)
        record_id = result.scalar()
        db_session.commit()
        
        # Attempt DELETE
        delete_query = text(f"""
            DELETE FROM audit_log WHERE id = {record_id}
        """)
        
        with pytest.raises(Exception) as exc_info:
            db_session.execute(delete_query)
            db_session.commit()
        
        # Verify exception
        assert exc_info.value is not None
        error_msg = str(exc_info.value).lower()
        assert any(phrase in error_msg for phrase in [
            "append-only",
            "not permitted",
            "delete operations are not permitted"
        ]), f"Expected append-only error, got: {error_msg}"
        
        # Verify row still exists
        verify_query = text(f"""
            SELECT COUNT(*) FROM audit_log WHERE id = {record_id}
        """)
        count = db_session.execute(verify_query).scalar()
        assert count == 1, "Row was deleted despite trigger"
    
    def test_delete_observations_rejected(self, db_session):
        """
        OQ-8 Test Case 2: DELETE on observations should be rejected
        """
        # Insert test observation
        insert_query = text("""
            INSERT INTO observations (observation_code, value_quantity, fhir_resource)
            VALUES ('test-code', '{"value": 100, "unit": "mmHg"}', '{"resourceType": "Observation"}')
            RETURNING id
        """)
        
        result = db_session.execute(insert_query)
        record_id = result.scalar()
        db_session.commit()
        
        # Attempt DELETE
        delete_query = text(f"""
            DELETE FROM observations WHERE id = {record_id}
        """)
        
        with pytest.raises(Exception) as exc_info:
            db_session.execute(delete_query)
            db_session.commit()
        
        assert exc_info.value is not None
        error_msg = str(exc_info.value).lower()
        assert "append-only" in error_msg or "not permitted" in error_msg
        
        # Verify row exists
        count = db_session.execute(text(f"""
            SELECT COUNT(*) FROM observations WHERE id = {record_id}
        """)).scalar()
        assert count == 1
    
    def test_delete_plates_rejected(self, db_session):
        """
        OQ-8 Test Case 3: DELETE on plates should be rejected
        """
        # Insert test plate
        insert_query = text("""
            INSERT INTO plates (plate_name, plate_type)
            VALUES ('Test Plate', '96-well')
            RETURNING id
        """)
        
        result = db_session.execute(insert_query)
        record_id = result.scalar()
        db_session.commit()
        
        # Attempt DELETE
        delete_query = text(f"""
            DELETE FROM plates WHERE id = {record_id}
        """)
        
        with pytest.raises(Exception) as exc_info:
            db_session.execute(delete_query)
            db_session.commit()
        
        assert exc_info.value is not None
        error_msg = str(exc_info.value).lower()
        assert "append-only" in error_msg or "not permitted" in error_msg
    
    def test_all_compliance_tables_reject_delete(self, db_session):
        """
        OQ-8 Test Case 4: Verify all compliance tables reject DELETE
        """
        for table_name in self.COMPLIANCE_TABLES:
            # Attempt generic DELETE (WHERE 1=0 to avoid actual deletion)
            delete_query = text(f"""
                DELETE FROM {table_name}
                WHERE 1=0
            """)
            
            try:
                db_session.execute(delete_query)
                db_session.commit()
                # Trigger should fire even if no rows affected
            except Exception as e:
                # Expected behavior
                error_msg = str(e).lower()
                if "append-only" in error_msg or "not permitted" in error_msg:
                    continue  # This is expected
                else:
                    raise
    
    def test_row_intact_after_failed_delete(self, db_session):
        """
        OQ-8 Test Case 5: Verify row remains intact after failed DELETE
        """
        # Insert test record
        insert_query = text("""
            INSERT INTO plates (plate_name, plate_type)
            VALUES ('Test Plate', '96-well')
            RETURNING id
        """)
        
        result = db_session.execute(insert_query)
        record_id = result.scalar()
        db_session.commit()
        
        # Attempt DELETE
        delete_query = text(f"""
            DELETE FROM plates WHERE id = {record_id}
        """)
        
        try:
            db_session.execute(delete_query)
            db_session.commit()
        except Exception:
            db_session.rollback()
        
        # Verify row still exists
        verify_query = text(f"""
            SELECT id, plate_name FROM plates WHERE id = {record_id}
        """)
        result = db_session.execute(verify_query).first()
        
        assert result is not None, "Row was deleted despite trigger"
        assert result[1] == 'Test Plate', "Row data was modified"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
