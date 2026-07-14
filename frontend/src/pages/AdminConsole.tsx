import React, { useState, useEffect } from 'react'
import './AdminConsole.css'

/**
 * AdminConsole Component
 * Implements SRS - Admin Console for system configuration
 * 
 * Features:
 * - JWT key rotation (SRS §3.6)
 * - EMA α parameter tuning (SRS FR-3.5.1)
 * - Pulse Engine controls (SRS C1)
 * - System status monitoring
 */
const AdminConsole: React.FC = () => {
  const [jwtSecret, setJwtSecret] = useState('')
  const [tokenExpiry, setTokenExpiry] = useState(24)
  const [emaAlpha, setEmaAlpha] = useState(0.5)
  const [concurrentPatients, setConcurrentPatients] = useState(10)
  const [systemStatus, setSystemStatus] = useState({
    database: 'unknown',
    middleware: 'unknown',
    pulseEngine: 'unknown'
  })

  // Fetch system status
  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch('/api/health')
        const data = await response.json()
        setSystemStatus({
          database: data.database || 'unknown',
          middleware: data.middleware || 'unknown',
          pulseEngine: data.pulseEngine || 'unknown'
        })
      } catch (error) {
        console.error('Failed to fetch system status:', error)
      }
    }
    
    fetchStatus()
    const interval = setInterval(fetchStatus, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  // Rotate JWT keys
  const rotateJwtKeys = async () => {
    try {
      const response = await fetch('/api/admin/jwt/rotate', { method: 'POST' })
      const data = await response.json()
      alert(data.message || 'JWT keys rotated successfully')
    } catch (error) {
      alert('Failed to rotate JWT keys')
    }
  }

  // Update EMA parameter
  const updateEmaParameter = async () => {
    try {
      const response = await fetch('/api/admin/signal/ema', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ alpha: emaAlpha })
      })
      const data = await response.json()
      alert(data.message || 'EMA parameter updated')
    } catch (error) {
      alert('Failed to update EMA parameter')
    }
  }

  // Restart Pulse Engine
  const restartPulseEngine = async () => {
    if (!confirm('Are you sure you want to restart the Pulse Engine?')) return
    
    try {
      const response = await fetch('/api/admin/pulse/restart', { method: 'POST' })
      const data = await response.json()
      alert(data.message || 'Pulse Engine restart initiated')
    } catch (error) {
      alert('Failed to restart Pulse Engine')
    }
  }

  // Get status class
  const getStatusClass = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'running':
        return 'status-healthy'
      case 'degraded':
        return 'status-degraded'
      default:
        return 'status-unhealthy'
    }
  }

  return (
    <div className="admin-console">
      <h2>Admin Console</h2>

      <div className="admin-sections">
        {/* JWT Configuration */}
        <section className="admin-section">
          <h3>🔐 JWT Configuration</h3>
          <div className="form-group">
            <label>JWT Secret:</label>
            <input
              type="password"
              value={jwtSecret}
              onChange={(e) => setJwtSecret(e.target.value)}
              placeholder="Enter new JWT secret"
            />
          </div>
          <div className="form-group">
            <label>Token Expiration (hours):</label>
            <input
              type="number"
              value={tokenExpiry}
              onChange={(e) => setTokenExpiry(Number(e.target.value))}
              min={1}
              max={168}
            />
          </div>
          <button onClick={rotateJwtKeys} className="btn-warning">
            Rotate Keys
          </button>
        </section>

        {/* Signal Processing */}
        <section className="admin-section">
          <h3>📊 Signal Processing</h3>
          <div className="form-group">
            <label>EMA Alpha Parameter (α):</label>
            <input
              type="range"
              min={0.1}
              max={1.0}
              step={0.1}
              value={emaAlpha}
              onChange={(e) => setEmaAlpha(Number(e.target.value))}
            />
            <span>{emaAlpha.toFixed(1)}</span>
            <p className="form-hint">
              Higher α = more responsive, Lower α = smoother
            </p>
          </div>
          <button onClick={updateEmaParameter} className="btn-primary">
            Update Parameter
          </button>
        </section>

        {/* Pulse Engine */}
        <section className="admin-section">
          <h3>⚙️ Pulse Engine</h3>
          <div className="form-group">
            <label>Concurrent Patients:</label>
            <input
              type="number"
              value={concurrentPatients}
              onChange={(e) => setConcurrentPatients(Number(e.target.value))}
              min={1}
              max={100}
            />
          </div>
          <button onClick={restartPulseEngine} className="btn-danger">
            Restart Engine
          </button>
        </section>

        {/* System Status */}
        <section className="admin-section">
          <h3>🖥️ System Status</h3>
          <div className="status-grid">
            <div className="status-item">
              <span className="status-label">Database:</span>
              <span className={`status-value ${getStatusClass(systemStatus.database)}`}>
                {systemStatus.database === 'healthy' ? '✓ Healthy' : systemStatus.database === 'degraded' ? '⚠ Degraded' : '✗ Unknown'}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">Middleware:</span>
              <span className={`status-value ${getStatusClass(systemStatus.middleware)}`}>
                {systemStatus.middleware === 'healthy' ? '✓ Healthy' : systemStatus.middleware === 'degraded' ? '⚠ Degraded' : '✗ Unknown'}
              </span>
            </div>
            <div className="status-item">
              <span className="status-label">Pulse Engine:</span>
              <span className={`status-value ${getStatusClass(systemStatus.pulseEngine)}`}>
                {systemStatus.pulseEngine === 'running' ? '✓ Running' : systemStatus.pulseEngine === 'degraded' ? '⚠ Degraded' : '✗ Unknown'}
              </span>
            </div>
          </div>
        </section>
      </div>
    </div>
  )
}

export default AdminConsole
