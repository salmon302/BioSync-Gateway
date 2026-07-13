import React from 'react'
import './AdminConsole.css'

/**
 * AdminConsole Component
 * Implements SRS - Admin Console for system configuration
 * 
 * Stub implementation for Phase 0
 * Full implementation in Phase 3
 */
const AdminConsole: React.FC = () => {
  return (
    <div className="admin-console">
      <h2>Admin Console</h2>
      <p className="placeholder-text">
        Phase 0: Stub component - Full implementation in Phase 3
      </p>

      <div className="admin-sections">
        <section className="admin-section">
          <h3>JWT Configuration</h3>
          <div className="form-group">
            <label>JWT Secret:</label>
            <input type="password" disabled placeholder="Configured via environment" />
          </div>
          <div className="form-group">
            <label>Token Expiration (hours):</label>
            <input type="number" disabled value={24} />
          </div>
          <button disabled>Rotate Keys</button>
        </section>

        <section className="admin-section">
          <h3>Signal Processing</h3>
          <div className="form-group">
            <label>EMA Alpha Parameter:</label>
            <input type="number" disabled step="0.1" value={0.5} />
          </div>
          <button disabled>Update Parameter</button>
        </section>

        <section className="admin-section">
          <h3>Pulse Engine</h3>
          <div className="form-group">
            <label>Concurrent Patients:</label>
            <input type="number" disabled value={10} />
          </div>
          <button disabled>Restart Engine</button>
        </section>

        <section className="admin-section">
          <h3>System Status</h3>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Database:</span>
              <span className="status-value">Unknown</span>
            </div>
            <div className="status-item">
              <span className="status-label">Middleware:</span>
              <span className="status-value">Unknown</span>
            </div>
            <div className="status-item">
              <span className="status-label">Pulse Engine:</span>
              <span className="status-value">Unknown</span>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

export default AdminConsole
