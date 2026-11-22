import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function Onboarding() {
  const navigate = useNavigate()
  const [existingSessions, setExistingSessions] = useState([])
  const [form, setForm] = useState({
    name: '',
    subject: '',
    available_minutes_per_day: 60,
    goal_score: 85,
    level: 'beginner',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.listStudents()
      .then((data) => {
        if (data && data.length > 0) {
          setExistingSessions(data)
          // Prefill user's name from previous session
          setForm((f) => ({ ...f, name: data[0].name, subject: '' }))
        } else {
          setForm((f) => ({ ...f, subject: 'Natural Language Processing' }))
        }
      })
      .catch(() => {})
  }, [])

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
    <div className="shell" style={{ maxWidth: '640px', paddingTop: '3rem' }}>
      <div className="card" style={{ padding: '2.2rem' }}>
        <h1 style={{ fontSize: '1.75rem', marginBottom: '0.4rem' }}>
          {existingSessions.length > 0 ? 'Start a New Study Topic 📚' : 'Setup Your Learning Profile 🎯'}
        </h1>
        <p style={{ marginBottom: '1.5rem' }}>
          {existingSessions.length > 0
            ? 'Add another subject or course (e.g. Operating Systems, Computer Networks). You can switch between topics anytime.'
            : 'StudyMate configures an adaptive knowledge graph based on your subject, daily availability, and target goals.'}
        </p>

        <form onSubmit={handleSubmit}>
          <label htmlFor="name">Your Name</label>
          <input id="name" required placeholder="e.g. Alex Sharma" value={form.name} onChange={(e) => update('name', e.target.value)} />

          <label htmlFor="subject">Subject or Topic to Study</label>
          <input id="subject" required placeholder="e.g. Operating Systems or Machine Learning" value={form.subject} onChange={(e) => update('subject', e.target.value)} />

          <div className="field-row">
            <div>
              <label htmlFor="level">Proficiency Level</label>
              <select id="level" value={form.level} onChange={(e) => update('level', e.target.value)}>
                <option value="beginner">Beginner (Foundations first)</option>
                <option value="intermediate">Intermediate (Standard)</option>
                <option value="advanced">Advanced (Deep dive)</option>
              </select>
            </div>
            <div>
              <label htmlFor="minutes">Minutes Available / Day</label>
              <input id="minutes" type="number" min={15} max={300} value={form.available_minutes_per_day}
                onChange={(e) => update('available_minutes_per_day', Number(e.target.value))} />
            </div>
          </div>

          <label htmlFor="goal">Target Mastery Goal ({form.goal_score}%)</label>
          <input id="goal" type="range" min={60} max={100} value={form.goal_score}
            onChange={(e) => update('goal_score', Number(e.target.value))} style={{ padding: 0 }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-light)', marginTop: '0.2rem' }}>
            <span>60% (Pass)</span>
            <span>85% (Target)</span>
            <span>100% (Mastery)</span>
          </div>

          {error && (
            <p style={{ color: 'var(--danger-text)', background: 'var(--danger-soft)', padding: '0.65rem', borderRadius: '6px', marginTop: '1rem', fontSize: '0.88rem' }}>
              {error}
            </p>
          )}

          <div style={{ marginTop: '2rem', display: 'flex', gap: '0.8rem' }}>
            <button type="submit" disabled={loading} style={{ flex: 1, padding: '0.8rem', fontSize: '1rem' }}>
              {loading ? 'Initializing Topic…' : 'Enter Study Dashboard ➔'}
            </button>
            {existingSessions.length > 0 && (
              <button
                type="button"
                className="secondary"
                style={{ padding: '0.8rem 1.2rem', fontSize: '0.95rem' }}
                onClick={() => navigate(`/dashboard/${existingSessions[0].id}`)}
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  )
}
