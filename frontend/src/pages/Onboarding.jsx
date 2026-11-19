import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function Onboarding() {
  const navigate = useNavigate()
  const [form, setForm] = useState({
    name: '',
    subject: 'NLP',
    available_minutes_per_day: 60,
    goal_score: 85,
    level: 'beginner',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  function update(field, value) {
    setForm((f) => ({ ...f, [field]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const student = await api.createStudent(form)
      navigate(`/dashboard/${student.id}`)
    } catch (err) {
      setError('Could not reach the backend. Is it running on localhost:8000?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="shell">
      <h1>Tell us what you're studying</h1>
      <p>
        The agent uses this to build your initial plan — everything after
        this adapts automatically as you learn.
      </p>

      <form onSubmit={handleSubmit}>
        <label htmlFor="name">Your name</label>
        <input id="name" required value={form.name} onChange={(e) => update('name', e.target.value)} />

        <label htmlFor="subject">Subject</label>
        <input id="subject" required value={form.subject} onChange={(e) => update('subject', e.target.value)} />

        <div className="field-row">
          <div>
            <label htmlFor="level">Current level</label>
            <select id="level" value={form.level} onChange={(e) => update('level', e.target.value)}>
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
            </select>
          </div>
          <div>
            <label htmlFor="minutes">Minutes available per day</label>
            <input
              id="minutes" type="number" min="10" value={form.available_minutes_per_day}
              onChange={(e) => update('available_minutes_per_day', Number(e.target.value))}
            />
          </div>
        </div>

        <label htmlFor="goal">Goal score (%)</label>
        <input
          id="goal" type="number" min="1" max="100" value={form.goal_score}
          onChange={(e) => update('goal_score', Number(e.target.value))}
        />

        {error && <p style={{ color: 'var(--alert)', marginTop: '1em' }}>{error}</p>}

        <div style={{ marginTop: '2em' }}>
          <button type="submit" disabled={loading}>
            {loading ? 'Setting up…' : 'Start learning'}
          </button>
        </div>
      </form>
    </div>
  )
}
