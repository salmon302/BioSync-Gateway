import React, { useState, useEffect } from 'react'
import { Link, useLocation } from 'react-router-dom'
import './Navigation.css'
import { LoginModal } from './LoginModal'

const Navigation: React.FC = () => {
  const location = useLocation()
  const [showLogin, setShowLogin] = useState(false)
  const [user, setUser] = useState<string | null>(null)

  // Reflect persisted JWT (stored by LoginModal / utils/api.ts).
  useEffect(() => {
    const token = localStorage.getItem('biosync_jwt')
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]))
        setUser(payload.sub || 'user')
      } catch {
        setUser(null)
      }
    }
  }, [])

  const handleLogin = (username: string) => setUser(username)
  const handleLogout = () => {
    localStorage.removeItem('biosync_jwt')
    setUser(null)
  }

  const navItems = [
    { path: '/telemetry', label: 'Telemetry Dashboard' },
    { path: '/plates', label: 'Microplate Editor' },
    { path: '/audit', label: 'Audit Viewer' },
    { path: '/admin', label: 'Admin Console' }
  ]

  return (
    <nav className="navigation">
      <div className="nav-brand">
        <h1>BioSync-Gateway</h1>
      </div>
      <ul className="nav-list">
        {navItems.map(item => (
          <li key={item.path} className={location.pathname === item.path ? 'active' : ''}>
            <Link to={item.path}>{item.label}</Link>
          </li>
        ))}
      </ul>
      <div className="nav-auth">
        {user ? (
          <>
            <span className="nav-user">Signed in: {user}</span>
            <button onClick={handleLogout}>Sign out</button>
          </>
        ) : (
          <button onClick={() => setShowLogin(true)}>Sign in</button>
        )}
      </div>
      {showLogin && (
        <LoginModal onClose={() => setShowLogin(false)} onLogin={handleLogin} />
      )}
    </nav>
  )
}

export default Navigation
