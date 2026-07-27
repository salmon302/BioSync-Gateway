// SPDX-License-Identifier: MIT
/**
 * Login modal for BioSync-Gateway frontend.
 * Posts credentials to the middleware auth endpoint and stores the returned
 * JWT in localStorage ('biosync_jwt') so `utils/api.ts` can attach it as a
 * Bearer token. This closes the frontend-auth gap needed for FR-3.2.3
 * (well-click -> authenticated FHIR Observation fetch).
 */

import React, { useState } from 'react'
import { apiFetch } from '../utils/api'

interface LoginModalProps {
  onClose: () => void
  onLogin: (username: string) => void
}

export const LoginModal: React.FC<LoginModalProps> = ({ onClose, onLogin }) => {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = await apiFetch<{ access_token: string; expires_in: number }>(
        '/auth/login',
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        }
      )
      localStorage.setItem('biosync_jwt', res.access_token)
      onLogin(username)
      onClose()
    } catch (err: any) {
      setError(err?.message ?? 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="login-title">
      <div className="login-modal">
        <h3 id="login-title">Sign in</h3>
        <form onSubmit={submit}>
          <label>
            Username
            <input
              value={username}
              onChange={e => setUsername(e.target.value)}
              autoFocus
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={e => setPassword(e.target.value)}
            />
          </label>
          {error && <p className="obs-error">{error}</p>}
          <div className="login-actions">
            <button type="button" onClick={onClose}>Cancel</button>
            <button type="submit" disabled={loading}>
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default LoginModal
