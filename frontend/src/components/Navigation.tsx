import React from 'react'
import { Link, useLocation } from 'react-router-dom'
import './Navigation.css'

const Navigation: React.FC = () => {
  const location = useLocation()

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
    </nav>
  )
}

export default Navigation
