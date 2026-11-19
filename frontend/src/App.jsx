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
        <Link to="/" className="brand" style={{ textDecoration: 'none' }}>
          <span>🎓</span>
          <span>StudyMate</span>
        </Link>
        <span className="tagline">· Agentic NLP Study Assistant</span>
        {signedIn && (
          <button className="secondary" style={{ marginLeft: 'auto', padding: '0.4rem 0.9rem', fontSize: '0.85rem' }} onClick={signOut}>
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
