import React, { useState } from 'react'
import './AuditViewer.css'

/**
 * AuditViewer Component
 * Implements SRS §3.8 - Audit Trail Viewer
 * 
 * Stub implementation for Phase 0
 * Full implementation in Phase 3
 */
interface AuditEntry {
  id: number
  tableName: string
  operation: string
  recordId: number
  timestamp: string
  userId: string
  previousHash: string
  currentHash: string
  integrityStatus: 'valid' | 'broken'
}

const AuditViewer: React.FC = () => {
  const [auditEntries] = useState<AuditEntry[]>([])
  const [integrityStatus] = useState<'ok' | 'broken'>('ok')

  return (
    <div className="audit-viewer">
      <h2>Audit Trail Viewer</h2>
      <p className="placeholder-text">
        Phase 0: Stub component - Full implementation in Phase 3
      </p>

      <div className="audit-controls">
        <button disabled>Verify Chain</button>
        <span className={`integrity-badge ${integrityStatus}`}>
          {integrityStatus === 'ok' ? '✓ Chain Integrity OK' : '✗ Chain Broken'}
        </span>
      </div>

      <div className="audit-table-container">
        <table className="audit-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Table</th>
              <th>Operation</th>
              <th>Record ID</th>
              <th>Timestamp</th>
              <th>User</th>
              <th>Hash Status</th>
            </tr>
          </thead>
          <tbody>
            {auditEntries.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  No audit entries yet. Chain verification will appear here.
                </td>
              </tr>
            ) : (
              auditEntries.map(entry => (
                <tr key={entry.id}>
                  <td>{entry.id}</td>
                  <td>{entry.tableName}</td>
                  <td>{entry.operation}</td>
                  <td>{entry.recordId}</td>
                  <td>{entry.timestamp}</td>
                  <td>{entry.userId}</td>
                  <td>
                    <span className={`hash-status ${entry.integrityStatus}`}>
                      {entry.integrityStatus === 'valid' ? '✓' : '✗'}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default AuditViewer
