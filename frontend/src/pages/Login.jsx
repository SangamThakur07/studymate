import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, auth } from '../api/client.js'

export default function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login') // 'login' | 'register'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const res = mode === 'login' ? await api.login(email, password) : await api.register(email, password)
      auth.setToken(res.access_token)
      // returning students go straight to their dashboard; new accounts set up a profile first
      navigate(res.students && res.students.length ? `/dashboard/${res.students[0].id}` : '/')
    } catch (err) {
      setError(err.message || 'Something went wrong. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="shell" style={{ maxWidth: '480px', paddingTop: '4rem' }}>
      <div className="card" style={{ padding: '2.2rem' }}>
        <div style={{ textAlign: 'center', marginBottom: '1.5rem' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '0.4rem' }}>🎓</div>
          <h1 style={{ fontSize: '1.75rem', marginBottom: '0.3rem' }}>
            {mode === 'login' ? 'Sign in to StudyMate' : 'Create your account'}
          </h1>
          <p style={{ margin: 0, fontSize: '0.92rem' }}>
            {mode === 'login'
              ? 'Access your saved notes, knowledge graph, and mastery metrics.'
              : 'Start learning with an autonomous NLP agent personalized to your notes.'}
          </p>
        </div>

        <form onSubmit={handleSubmit}>
          <label htmlFor="email">Email address</label>
          <input id="email" type="email" required autoComplete="email" placeholder="student@university.edu" value={email}
            onChange={(e) => setEmail(e.target.value)} />

          <label htmlFor="password">Password {mode === 'register' && '(min. 8 characters)'}</label>
          <input id="password" type="password" required minLength={mode === 'register' ? 8 : undefined}
            placeholder="••••••••"
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} />

          {error && (
            <p style={{ color: 'var(--danger-text)', background: 'var(--danger-soft)', padding: '0.65rem', borderRadius: '6px', marginTop: '1rem', fontSize: '0.88rem' }}>
              {error}
            </p>
          )}

          <div style={{ marginTop: '1.8rem', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
            <button type="submit" disabled={loading} style={{ width: '100%', padding: '0.75rem' }}>
              {loading ? 'Authenticating…' : mode === 'login' ? 'Sign in' : 'Create Account'}
            </button>
            <button type="button" className="secondary" style={{ width: '100%', padding: '0.7rem' }}
              onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
              {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
