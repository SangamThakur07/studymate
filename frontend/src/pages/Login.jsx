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
    <div className="shell">
      <h1>{mode === 'login' ? 'Sign in' : 'Create your account'}</h1>
      <p>
        {mode === 'login'
          ? 'Welcome back. Your notes, topics and progress are saved to your account.'
          : 'Your uploaded notes and progress stay private to your account.'}
      </p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="email">Email</label>
        <input id="email" type="email" required autoComplete="email" value={email}
          onChange={(e) => setEmail(e.target.value)} />

        <label htmlFor="password">Password {mode === 'register' && '(at least 8 characters)'}</label>
        <input id="password" type="password" required minLength={mode === 'register' ? 8 : undefined}
          autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          value={password} onChange={(e) => setPassword(e.target.value)} />

        {error && <p style={{ color: 'var(--alert)', marginTop: '1em' }}>{error}</p>}

        <div style={{ marginTop: '1.6em', display: 'flex', gap: '0.8rem', alignItems: 'center' }}>
          <button type="submit" disabled={loading}>
            {loading ? 'Please wait…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
          <button type="button" className="secondary"
            onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(null) }}>
            {mode === 'login' ? 'I need an account' : 'I already have an account'}
          </button>
        </div>
      </form>
    </div>
  )
}
