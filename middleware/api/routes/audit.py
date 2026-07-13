"""
Audit Log Routes
Implements SRS §3.8 - Audit Trail and Hash Chain
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import text, func
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import logging

from api.auth import get_current_user, require_scope
from database import get_db
from engine.hash_chain import compute_hash, verify_chain, get_genesis_hash

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/")
async def get_audit_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    table_name: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_read"))
):
    """
    Retrieve paginated audit logs with filtering.
    Requires audit_read scope.
    Implements OQ-7/8/9 verification endpoints.
    """
    try:
        # Build query with filters
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = {}
        
        if table_name:
            query += " AND table_name = :table_name"
            params["table_name"] = table_name
        
        if operation:
            query += " AND operation = :operation"
            params["operation"] = operation
        
        if start_date:
            query += " AND timestamp >= :start_date"
            params["start_date"] = start_date
        
        if end_date:
            query += " AND timestamp <= :end_date"
            params["end_date"] = end_date
        
        # Get total count
        count_query = f"SELECT COUNT(*) FROM ({query}) AS count_query"
        total = db.execute(text(count_query), params).scalar()
        
        # Add pagination
        query += " ORDER BY id DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = (page - 1) * limit
        
        # Execute query
        result = db.execute(text(query), params)
        logs = [dict(row._mapping) for row in result]
        
        return {
            "page": page,
            "limit": limit,
            "total": total,
            "total_pages": (total + limit - 1) // limit,
            "logs": logs
        }
    
    except Exception as e:
        logger.error(f"Error retrieving audit logs: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit logs")


@router.get("/verify")
async def verify_hash_chain(
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_read"))
):
    """
    Verify integrity of hash chain.
    Returns integrity status and broken row if detected.
    Implements SRS FR-3.8.3
    """
    try:
        # Call database function to verify chain
        result = db.execute(text("SELECT * FROM verify_hash_chain()"))
        row = result.first()
        
        if row:
            integrity_status = row[0]
            broken_at_row_id = row[1]
            
            return {
                "integrity": integrity_status,
                "broken_at_row_id": broken_at_row_id,
                "verification_timestamp": datetime.utcnow().isoformat()
            }
        
        return {
            "integrity": "unknown",
            "broken_at_row_id": None,
            "verification_timestamp": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error verifying hash chain: {e}")
        raise HTTPException(status_code=500, detail="Failed to verify hash chain")


@router.get("/statistics")
async def get_audit_statistics(
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_read"))
):
    """
    Get audit log statistics.
    Returns counts by table, operation, and time range.
    """
    try:
        stats_query = """
            SELECT 
                table_name,
                operation,
                COUNT(*) as count,
                MIN(timestamp) as first_entry,
                MAX(timestamp) as last_entry
            FROM audit_log
            GROUP BY table_name, operation
            ORDER BY table_name, operation
        """
        
        result = db.execute(text(stats_query))
        stats = [dict(row._mapping) for row in result]
        
        # Get total entries
        total = db.execute(text("SELECT COUNT(*) FROM audit_log")).scalar()
        
        return {
            "total_entries": total,
            "statistics": stats
        }
    
    except Exception as e:
        logger.error(f"Error retrieving audit statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@router.post("/test-trigger")
async def test_append_only_trigger(
    table_name: str = Query(..., description="Table to test (e.g., 'observations')"),
    db: Session = Depends(get_db),
    current_user=Depends(require_scope("audit_write"))
):
    """
    Test append-only trigger by attempting UPDATE/DELETE.
    Used for OQ-7 and OQ-8 verification.
    """
    try:
        # Attempt to UPDATE a non-existent record (should fail)
        update_query = f"UPDATE {table_name} SET id = id WHERE 1=0"
        db.execute(text(update_query))
        db.commit()
        
        return {
            "status": "error",
            "message": f"UPDATE trigger on {table_name} did not prevent operation"
        }
    
    except Exception as e:
        # Expected: trigger should prevent UPDATE
        error_msg = str(e)
        if "append-only" in error_msg.lower() or "not permitted" in error_msg.lower():
            return {
                "status": "pass",
                "message": f"UPDATE trigger on {table_name} correctly prevented operation",
                "error": error_msg
            }
        else:
            return {
                "status": "error",
                "message": f"Unexpected error testing {table_name}",
                "error": error_msg
            }
