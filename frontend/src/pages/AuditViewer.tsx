import React, { useState, useEffect, useCallback } from 'react'
import './AuditViewer.css'

/**
 * AuditViewer Component
 * Implements SRS §3.8 - Audit Trail Viewer
 * 
 * Features:
 * - Sortable/filterable table (SRS FR-3.8.4)
 * - Hash chain integrity indicator (SRS FR-3.8.5)
 * - "Verify Chain" button → calls GET /api/audit/verify (SRS FR-3.8.6)
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
  integrityStatus: 'valid' | 'broken' | 'unknown'
}

const AuditViewer: React.FC = () => {
  const [auditEntries, setAuditEntries] = useState<AuditEntry[]>([])
  const [integrityStatus, setIntegrityStatus] = useState<'ok' | 'broken' | 'checking'>('checking')
  const [page, setPage] = useState(1)
  const [pageSize] = useState(50)
  const [totalEntries, setTotalEntries] = useState(0)
  const [sortField, setSortField] = useState<keyof AuditEntry>('timestamp')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')
  const [filterTable, setFilterTable] = useState<string>('')

  // Fetch audit entries
  const fetchAuditEntries = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        pageSize: pageSize.toString(),
        sort: sortField,
        direction: sortDirection
      })
      
      if (filterTable) {
        params.append('table', filterTable)
      }
      
      const response = await fetch(`/api/audit?${params}`)
      const data = await response.json()
      
      setAuditEntries(data.entries || [])
      setTotalEntries(data.total || 0)
    } catch (error) {
      console.error('Failed to fetch audit entries:', error)
    }
  }, [page, pageSize, sortField, sortDirection, filterTable])

  // Verify hash chain
  const verifyChain = useCallback(async () => {
    try {
      setIntegrityStatus('checking')
      const response = await fetch('/api/audit/verify')
      const data = await response.json()
      
      if (data.integrity === 'ok') {
        setIntegrityStatus('ok')
      } else {
        setIntegrityStatus('broken')
      }
    } catch (error) {
      console.error('Failed to verify chain:', error)
      setIntegrityStatus('broken')
    }
  }, [])

  // Load data on mount
  useEffect(() => {
    fetchAuditEntries()
    verifyChain()
  }, [fetchAuditEntries, verifyChain])

  // Handle sort
  const handleSort = (field: keyof AuditEntry) => {
    if (field === sortField) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortDirection('asc')
    }
  }

  // Render sort indicator
  const renderSortIndicator = (field: keyof AuditEntry) => {
    if (field !== sortField) return null
    return sortDirection === 'asc' ? ' ↑' : ' ↓'
  }

  return (
    <div className="audit-viewer">
      <div className="audit-header">
        <h2>Audit Trail Viewer</h2>
        <div className="audit-controls">
          <button onClick={verifyChain} className="verify-btn">
            {integrityStatus === 'checking' ? 'Checking...' : 'Verify Chain'}
          </button>
          <span className={`integrity-badge ${integrityStatus}`}>
            {integrityStatus === 'ok' && '✓ Chain Integrity OK'}
            {integrityStatus === 'broken' && '✗ Chain Broken'}
            {integrityStatus === 'checking' && '⟳ Checking...'}
          </span>
        </div>
      </div>

      <div className="audit-filters">
        <label>
          Filter by Table:
          <select value={filterTable} onChange={(e) => setFilterTable(e.target.value)}>
            <option value="">All Tables</option>
            <option value="audit_log">Audit Log</option>
            <option value="observations">Observations</option>
            <option value="plates">Plates</option>
            <option value="plate_wells">Plate Wells</option>
            <option value="devices">Devices</option>
            <option value="simulations">Simulations</option>
          </select>
        </label>
      </div>

      <div className="audit-table-container">
        <table className="audit-table">
          <thead>
            <tr>
              <th onClick={() => handleSort('id')} className="sortable">
                ID{renderSortIndicator('id')}
              </th>
              <th onClick={() => handleSort('tableName')} className="sortable">
                Table{renderSortIndicator('tableName')}
              </th>
              <th onClick={() => handleSort('operation')} className="sortable">
                Operation{renderSortIndicator('operation')}
              </th>
              <th onClick={() => handleSort('recordId')} className="sortable">
                Record ID{renderSortIndicator('recordId')}
              </th>
              <th onClick={() => handleSort('timestamp')} className="sortable">
                Timestamp{renderSortIndicator('timestamp')}
              </th>
              <th onClick={() => handleSort('userId')} className="sortable">
                User{renderSortIndicator('userId')}
              </th>
              <th>Hash Status</th>
            </tr>
          </thead>
          <tbody>
            {auditEntries.length === 0 ? (
              <tr>
                <td colSpan={7} className="empty-state">
                  No audit entries found.
                </td>
              </tr>
            ) : (
              auditEntries.map(entry => (
                <tr key={entry.id} className={entry.integrityStatus === 'broken' ? 'broken-row' : ''}>
                  <td>{entry.id}</td>
                  <td>{entry.tableName}</td>
                  <td>
                    <span className={`operation-badge ${entry.operation.toLowerCase()}`}>
                      {entry.operation}
                    </span>
                  </td>
                  <td>{entry.recordId}</td>
                  <td>{new Date(entry.timestamp).toLocaleString()}</td>
                  <td>{entry.userId}</td>
                  <td>
                    <span className={`hash-status ${entry.integrityStatus}`}>
                      {entry.integrityStatus === 'valid' && '✓ Valid'}
                      {entry.integrityStatus === 'broken' && '✗ Broken'}
                      {entry.integrityStatus === 'unknown' && '? Unknown'}
                    </span>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="audit-pagination">
        <button disabled={page === 1} onClick={() => setPage(p => Math.max(1, p - 1))}>
          Previous
        </button>
        <span>Page {page} of {Math.ceil(totalEntries / pageSize)}</span>
        <button 
          disabled={page >= Math.ceil(totalEntries / pageSize)} 
          onClick={() => setPage(p => p + 1)}
        >
          Next
        </button>
      </div>

      <div className="audit-info">
        <p>Total Entries: {totalEntries}</p>
        <p>Showing: {auditEntries.length} entries</p>
      </div>
    </div>
  )
}

export default AuditViewer
