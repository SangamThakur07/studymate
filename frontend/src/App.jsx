import { useState, useEffect } from 'react'
import { Routes, Route, Link, Navigate, useNavigate, useLocation } from 'react-router-dom'
import Onboarding from './pages/Onboarding.jsx'
import Dashboard from './pages/Dashboard.jsx'
import Login from './pages/Login.jsx'
import { api, auth } from './api/client.js'

function RequireAuth({ children }) {
  return auth.getToken() ? children : <Navigate to="/login" replace />
}

export default function App() {
  const navigate = useNavigate()
  const location = useLocation()
  const signedIn = !!auth.getToken()

  const [sessions, setSessions] = useState([])
  const [dropdownOpen, setDropdownOpen] = useState(false)

  // Fetch all user sessions when logged in
  useEffect(() => {
    if (signedIn) {
      api.listStudents()
        .then((data) => setSessions(data || []))
        .catch(() => {})
    } else {
      setSessions([])
    }
  }, [signedIn, location.pathname])

  // Detect active session ID from route
  const currentId = location.pathname.startsWith('/dashboard/')
    ? location.pathname.split('/dashboard/')[1]
    : null

  const activeSession = sessions.find((s) => String(s.id) === String(currentId))

  function signOut() {
    auth.clear()
    navigate('/login')
  }

  function handleSwitch(id) {
    setDropdownOpen(false)
    navigate(`/dashboard/${id}`)
  }

  function handleNewSession() {
    setDropdownOpen(false)
    navigate('/')
  }

  async function handleDelete(e, id) {
    e.stopPropagation()
    if (!window.confirm('Are you sure you want to delete this study topic and all its progress?')) return
    try {
      await api.deleteStudent(id)
      const updated = sessions.filter((s) => s.id !== id)
      setSessions(updated)
      if (String(currentId) === String(id)) {
        if (updated.length > 0) {
          navigate(`/dashboard/${updated[0].id}`)
        } else {
          navigate('/')
        }
      }
    } catch {
      alert('Could not delete session.')
    }
  }

  return (
    <>
      <nav className="top-nav" onClick={() => dropdownOpen && setDropdownOpen(false)}>
        <Link to="/" className="brand" style={{ textDecoration: 'none' }}>
          <span>🎓</span>
          <span>StudyMate</span>
        </Link>
        <span className="tagline">· Agentic NLP Study Assistant</span>

        {signedIn && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            {/* Session Switcher Dropdown */}
            {sessions.length > 0 && (
              <div className="session-dropdown-container" onClick={(e) => e.stopPropagation()}>
                <button
                  type="button"
                  className="session-btn"
                  onClick={() => setDropdownOpen((prev) => !prev)}
                  title="Switch study topic / session"
                >
                  <span>📚</span>
                  <span>{activeSession ? activeSession.subject : `Study Sessions (${sessions.length})`}</span>
                  <span style={{ fontSize: '0.75rem', opacity: 0.7 }}>{dropdownOpen ? '▲' : '▼'}</span>
                </button>

                {dropdownOpen && (
                  <div className="session-menu">
                    <div className="session-menu-header">
                      <span>Your Study Topics</span>
                      <span className="badge badge-primary" style={{ fontSize: '0.7rem' }}>{sessions.length} Active</span>
                    </div>

                    <div className="session-list">
                      {sessions.map((s) => (
                        <div
                          key={s.id}
                          className={`session-item ${String(s.id) === String(currentId) ? 'active' : ''}`}
                          onClick={() => handleSwitch(s.id)}
                        >
                          <div>
                            <div className="session-item-title">{s.subject}</div>
                            <div className="session-item-sub">
                              {s.name} · Goal: {s.goal_score}% · {s.level}
                            </div>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                            {String(s.id) === String(currentId) && (
                              <span style={{ color: 'var(--primary)', fontWeight: 'bold' }}>✓</span>
                            )}
                            <button
                              type="button"
                              onClick={(e) => handleDelete(e, s.id)}
                              style={{
                                background: 'transparent',
                                border: 'none',
                                color: '#94A3B8',
                                padding: '0.2rem 0.4rem',
                                cursor: 'pointer',
                                fontSize: '0.85rem',
                                boxShadow: 'none',
                              }}
                              title="Delete this topic"
                            >
                              ✕
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>

                    <div className="session-menu-footer">
                      <button
                        type="button"
                        onClick={handleNewSession}
                        style={{ width: '100%', padding: '0.45rem', fontSize: '0.82rem' }}
                      >
                        + Create New Study Topic
                      </button>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Direct "+ New Topic" button */}
            <button
              type="button"
              className="secondary"
              style={{ padding: '0.42rem 0.85rem', fontSize: '0.85rem' }}
              onClick={handleNewSession}
              title="Start a new subject or course"
            >
              + New Topic
            </button>

            {/* Sign Out */}
            <button
              type="button"
              className="secondary"
              style={{ padding: '0.42rem 0.85rem', fontSize: '0.85rem', color: '#64748B' }}
              onClick={signOut}
            >
              Sign out
            </button>
          </div>
        )}
      </nav>

      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/" element={<RequireAuth><Onboarding /></RequireAuth>} />
        <Route path="/new-session" element={<RequireAuth><Onboarding /></RequireAuth>} />
        <Route path="/dashboard/:studentId" element={<RequireAuth><Dashboard /></RequireAuth>} />
      </Routes>
    </>
  )
}
