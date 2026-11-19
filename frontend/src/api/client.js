// Backend address. In development the backend runs on port 8000; override with a
// VITE_API_URL environment variable when deploying.
// Development: backend on port 8000. Production build: same address the page was loaded from.
const BASE_URL = import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? '' : 'http://localhost:8000')
const TOKEN_KEY = 'studyToken'

export const auth = {
  getToken: () => localStorage.getItem(TOKEN_KEY),
  setToken: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
}

function authHeaders() {
  const t = auth.getToken()
  return t ? { Authorization: `Bearer ${t}` } : {}
}

async function handle(res) {
  if (res.status === 401 && auth.getToken()) {
    // session expired or token invalid: sign out and go to the login page
    auth.clear()
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let detail = ''
    try { detail = (await res.json()).detail } catch { detail = await res.text() }
    const err = new Error(typeof detail === 'string' && detail ? detail : `Request failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.json()
}

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(options.headers || {}) },
  })
  return handle(res)
}

export const api = {
  register: (email, password) => request('/auth/register', { method: 'POST', body: JSON.stringify({ email, password }) }),
  login: (email, password) => request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) }),
  me: () => request('/auth/me'),
  createStudent: (data) => request('/students/', { method: 'POST', body: JSON.stringify(data) }),
  progress: (studentId) => request(`/students/${studentId}/progress`),
  getProfile: (studentId) => request(`/students/${studentId}/profile`),
  nextAction: (studentId) => request(`/agent/${studentId}/next-action`),
  explain: (studentId) => request(`/agent/${studentId}/explain`, { method: 'POST' }),
  test: (studentId, questionType = 'mcq', n = 5) =>
    request(`/agent/${studentId}/test?question_type=${questionType}&n=${n}`, { method: 'POST' }),
  teach: (studentId, questionType = 'open') =>
    request(`/agent/${studentId}/teach?question_type=${questionType}`, { method: 'POST' }),
  submitAnswer: (payload) => request('/agent/answer', { method: 'POST', body: JSON.stringify(payload) }),
  uploadMaterial: async (studentId, file) => {
    const formData = new FormData()
    formData.append('file', file)
    const res = await fetch(`${BASE_URL}/students/${studentId}/materials/upload`, {
      method: 'POST',
      headers: authHeaders(), // no Content-Type: the browser sets the multipart boundary itself
      body: formData,
    })
    return handle(res)
  },
}
