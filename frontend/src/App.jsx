import { Routes, Route, Link, Navigate, useNavigate } from 'react-router-dom'
import Onboarding from './pages/Onboarding.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import { auth } from './api/client.js'

function RequireAuth({ children }) {
  return auth.getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  const navigate = useNavigate()
  const signedIn = !!auth.getToken()

  function signOut() {
    auth.clear()
    navigate('/login')
  }

  return (
    <>
      <nav className="top-nav">
        <Link to="/" className="brand" style={{ textDecoration: 'none', color: 'var(--ink)' }}>AI Study Assistant</Link>
        <span className="tagline">agentic AI study assistant</span>
        {signedIn && (
          <button className="secondary" style={{ marginLeft: 'auto', padding: '0.35em 0.9em' }} onClick={signOut}>
            Sign out
          </button>
        )}
      </nav>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Onboarding /></RequireAuth>} />
        <Route path="/dashboard/:studentId" element={<RequireAuth><Dashboard /></RequireAuth>} />
      </Routes>
    </>
  )
}
