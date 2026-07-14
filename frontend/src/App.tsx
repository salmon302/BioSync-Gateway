import { Routes, Route, Navigate } from 'react-router-dom'
import TelemetryDashboard from './pages/TelemetryDashboard'
import MicroplateEditor from './pages/MicroplateEditor'
import AuditViewer from './pages/AuditViewer'
import AdminConsole from './pages/AdminConsole'
import Navigation from './components/Navigation'

function App() {
  return (
    <div className="App">
      <Navigation />
      <main className="container">
        <Routes>
          <Route path="/" element={<Navigate to="/telemetry" replace />} />
          <Route path="/telemetry" element={<TelemetryDashboard />} />
          <Route path="/plates" element={<MicroplateEditor />} />
          <Route path="/audit" element={<AuditViewer />} />
          <Route path="/admin" element={<AdminConsole />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
