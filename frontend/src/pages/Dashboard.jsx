import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client.js'

export default function Dashboard() {
  const { studentId } = useParams()
  const navigate = useNavigate()
  const [profile, setProfile] = useState(null)
  const [decision, setDecision] = useState(null)
  const [progress, setProgress] = useState(null)
  const [pageError, setPageError] = useState(null)
  const [actionError, setActionError] = useState(null)

  // upload state
  const [uploading, setUploading] = useState(false)
  const [uploadResult, setUploadResult] = useState(null)
  const [uploadError, setUploadError] = useState(null)

  // study session: idle -> explained -> quiz -> result (per question) -> summary
  const [stage, setStage] = useState('idle')
  const [loading, setLoading] = useState(false)
  const [explanation, setExplanation] = useState(null)
  const [questions, setQuestions] = useState([])
  const [qIndex, setQIndex] = useState(0)
  const [answers, setAnswers] = useState([]) // one boolean per answered question
  const [answer, setAnswer] = useState('')
  const [selected, setSelected] = useState('')
  const [evaluation, setEvaluation] = useState(null)

  const refresh = useCallback(async () => {
    try {
      const [p, d, pr] = await Promise.all([api.getProfile(studentId), api.nextAction(studentId), api.progress(studentId)])
      setProfile(p)
      setDecision(d)
      setProgress(pr)
    } catch (err) {
      setPageError(err.status === 404
        ? "This study profile wasn't found in your account."
        : 'Could not reach the backend. Is it running on localhost:8000?')
    }
  }, [studentId])

  useEffect(() => { refresh() }, [refresh])

  function resetSession() {
    setStage('idle'); setExplanation(null); setQuestions([]); setQIndex(0)
    setAnswers([]); setAnswer(''); setSelected(''); setEvaluation(null)
  }

  async function handleFileUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true); setUploadError(null); setUploadResult(null); setActionError(null)
    try {
      setUploadResult(await api.uploadMaterial(studentId, file))
      resetSession()
      await refresh()
    } catch (err) {
      setUploadError(err.message || 'Upload failed.')
    } finally {
      setUploading(false)
      e.target.value = ''
    }
  }

  async function startSession() {
    setLoading(true)
    setActionError(null)
    try {
      const exp = await api.explain(studentId)
      setExplanation(exp)
      setStage('explained')
    } catch (err) {
      console.error(err)
      setActionError(err.message || 'Could not start a study session. Please try again.')
    } finally { setLoading(false) }
  }

  async function chooseTestType(type) {
    setLoading(true)
    setActionError(null)
    try {
      const res = await api.test(studentId, type, 5)
      setQuestions(res.questions); setQIndex(0); setAnswers([])
      setAnswer(''); setSelected(''); setEvaluation(null)
      setStage('quiz')
    } catch (err) {
      console.error(err)
      setActionError(err.message || 'Could not generate the test. Please try again.')
    } finally { setLoading(false) }
  }

  const quiz = questions[qIndex]
  const isMcq = quiz?.question_type === 'mcq'
  const canSubmit = isMcq ? !!selected : !!answer.trim()

  async function submit() {
    setLoading(true)
    setActionError(null)
    try {
      const result = await api.submitAnswer({
        student_id: Number(studentId),
        concept_name: quiz.concept_name,
        question: quiz.question,
        question_type: quiz.question_type,
        student_answer: isMcq ? '' : answer,
        selected_option: isMcq ? selected : '',
        correct_answer: isMcq ? quiz.correct_answer : '',
        references: isMcq ? [] : (quiz.references || []),
      })
      setEvaluation(result)
      setAnswers((a) => [...a, result.evaluation.score >= 6])
      setStage('result')
      await refresh()
    } catch (err) {
      console.error(err)
      setActionError(err.message || 'Could not submit your answer. Please try again.')
    } finally { setLoading(false) }
  }

  function nextQuestion() {
    if (qIndex + 1 < questions.length) {
      setQIndex(qIndex + 1); setAnswer(''); setSelected(''); setEvaluation(null)
      setStage('quiz')
    } else {
      setStage('summary')
    }
  }

  if (pageError) return (
    <div className="shell">
      <div className="card" style={{ borderColor: 'var(--danger)', background: 'var(--danger-soft)', textAlign: 'center', padding: '2.5rem 1.5rem' }}>
        <p style={{ color: 'var(--danger-text)', margin: '0 0 1.2rem 0', fontWeight: 600, fontSize: '1.05rem' }}>{pageError}</p>
        <button onClick={() => navigate('/')} style={{ padding: '0.6rem 1.2rem' }}>
          ← Back to Study Sessions
        </button>
      </div>
    </div>
  )

  if (!profile) return (
    <div className="shell">
      <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem' }}>
        <p className="loading-text" style={{ fontSize: '1.1rem', margin: 0 }}>Loading your study assistant…</p>
      </div>
    </div>
  )

  const masteryEntries = Object.entries(profile.mastery || {})
  const correctCount = answers.filter(Boolean).length
  const lastQuestion = qIndex + 1 >= questions.length

  return (
    <div className="shell">
      {actionError && (
        <div className="card" style={{
          borderColor: 'var(--danger)',
          background: 'var(--danger-soft)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '0.85rem 1.2rem',
          marginBottom: '1rem',
        }}>
          <p style={{ color: 'var(--danger-text)', margin: 0, fontWeight: 500, fontSize: '0.92rem' }}>
            ⚠️ {actionError}
          </p>
          <button
            className="secondary"
            onClick={() => setActionError(null)}
            style={{ padding: '0.3rem 0.65rem', fontSize: '0.82rem', marginLeft: '1rem' }}
          >
            ✕ Dismiss
          </button>
        </div>
      )}
      {/* Welcome Banner Card */}
      <div className="card" style={{ borderLeft: '4px solid var(--primary)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.8rem' }}>
          <div>
            <h1 style={{ marginBottom: '0.2rem' }}>Welcome back, {profile.name} 👋</h1>
            <p style={{ margin: 0 }}>
              Subject: <strong>{profile.subject}</strong> · Goal: <strong>{profile.goal_score}%</strong>
            </p>
          </div>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              type="button"
              className="secondary"
              style={{ padding: '0.35rem 0.8rem', fontSize: '0.82rem' }}
              onClick={() => navigate('/new-session')}
              title="Create a new study session for another subject"
            >
              + Study Another Topic
            </button>
            <span className="badge badge-primary">AI Powered</span>
            <span className="badge badge-success">Online</span>
          </div>
        </div>
      </div>

      {/* Agent Decision Card */}
      {decision && (
        <div className="decision-card">
          <div className="label">
            <span>🤖</span>
            <span>Agent Intelligence Engine</span>
          </div>
          <div style={{ fontSize: '1.15rem', fontWeight: 700, color: '#4C1D95', marginBottom: '0.3rem' }}>
            {decision.action === 'intervene' ? `Intervention: Focus on ${decision.concept}`
              : decision.action === 'review' ? `Spaced Revision: ${decision.concept}`
              : 'Knowledge State: Ready to Advance'}
          </div>
          <p style={{ margin: 0, color: '#5B21B6', fontSize: '0.92rem' }}>{decision.reasoning}</p>
        </div>
      )}

      {/* Study Material Upload Section */}
      <div className="card">
        <h2>📚 Study Material & RAG Indexing</h2>
        <p>Upload your notes or textbook (PDF). StudyMate extracts key concepts, builds your prerequisite graph, and indexes passages for semantic retrieval.</p>
        
        <label htmlFor="material-upload" className="upload-drop">
          <span style={{ fontSize: '2rem' }}>📄</span>
          <span style={{ fontWeight: 600 }}>{uploading ? 'Analyzing PDF & Extracting Key Concepts…' : 'Click to Upload Course Notes (PDF)'}</span>
          <span style={{ fontSize: '0.82rem', color: 'var(--text-light)' }}>Supports lecture slides, textbook excerpts, and study guides</span>
        </label>
        
        {uploading && (
          <p style={{ fontSize: '0.85rem', color: 'var(--primary)', marginTop: '0.8rem', textAlign: 'center' }}>
            Embedding notes with MiniLM-L6-v2 vector model. This builds the hybrid index for accurate semantic retrieval…
          </p>
        )}
        
        <input id="material-upload" type="file" accept="application/pdf"
          onChange={handleFileUpload} disabled={uploading} style={{ display: 'none' }} />
        
        {uploadError && (
          <p style={{ color: 'var(--danger-text)', background: 'var(--danger-soft)', padding: '0.6rem 0.8rem', borderRadius: '6px', marginTop: '0.8rem' }}>
            {uploadError}
          </p>
        )}
        
        {uploadResult && (
          <div style={{ background: 'var(--success-soft)', border: '1px solid #A7F3D0', borderRadius: '8px', padding: '1rem', marginTop: '1rem' }}>
            <div style={{ fontWeight: 700, color: 'var(--success-text)', marginBottom: '0.4rem' }}>
              ✓ Successfully indexed {uploadResult.concepts_extracted.length} concepts from {uploadResult.filename}
            </div>
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', margin: '0.4rem 0' }}>
              {uploadResult.concepts_extracted.map((c) => (
                <span key={c} className="badge badge-success" style={{ textTransform: 'none' }}>{c}</span>
              ))}
            </div>
            {uploadResult.seconds && (
              <p style={{ margin: '0.4rem 0 0 0', fontSize: '0.8rem', color: 'var(--success-text)' }}>
                Processing completed in {uploadResult.seconds.total}s. Passages indexed into vector database.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Mastery Progress Card */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <h2 style={{ margin: 0 }}>📊 Knowledge Mastery</h2>
          {progress && progress.topics.length > 0 && (
            <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
              <span className="badge badge-success">{progress.summary.strong} Strong</span>
              {progress.summary.due > 0 && <span className="badge badge-warning">{progress.summary.due} Due</span>}
              {progress.summary.weak > 0 && <span className="badge badge-danger">{progress.summary.weak} Weak</span>}
            </div>
          )}
        </div>

        {(!progress || progress.topics.length === 0) && (
          <p style={{ margin: 0 }}>No topics indexed yet. Upload a PDF above to initialize your learning graph.</p>
        )}

        {progress && progress.topics.length > 0 && (
          <>
            <div style={{ marginTop: '0.5rem' }}>
              {progress.topics.map((t) => (
                <div className="mastery-row" key={t.name}>
                  <div className="mastery-name">
                    <div>{t.name}</div>
                    <div className="mastery-status">
                      {t.status === 'new' && <span style={{ color: 'var(--text-light)' }}>Not started</span>}
                      {t.status === 'weak' && <span style={{ color: 'var(--danger)' }}>Needs practice</span>}
                      {t.status === 'due' && <span style={{ color: 'var(--warning)' }}>Due for review</span>}
                      {t.status === 'scheduled' && <span style={{ color: 'var(--success)' }}>On track</span>}
                    </div>
                  </div>
                  <div className="mastery-bar-track">
                    <div className={`mastery-bar-fill ${t.score < 60 ? 'weak' : ''}`} style={{ width: `${Math.min(t.score, 100)}%` }} />
                  </div>
                  <div className="mastery-pct">{Math.round(t.score)}%</div>
                </div>
              ))}
            </div>

            {progress.recent.length > 0 && (
              <details style={{ marginTop: '1.25rem', paddingTop: '0.85rem', borderTop: '1px solid var(--card-border)' }}>
                <summary style={{ cursor: 'pointer', fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-muted)' }}>
                  View Recent Assessment History ({progress.recent.length})
                </summary>
                <div style={{ marginTop: '0.6rem' }}>
                  {progress.recent.map((r, i) => (
                    <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0', fontSize: '0.88rem', borderBottom: '1px solid #F8FAFC' }}>
                      <span className={`badge ${r.correct ? 'badge-success' : 'badge-danger'}`} style={{ minWidth: '65px', textAlign: 'center' }}>
                        {r.correct ? 'Pass' : 'Review'}
                      </span>
                      <strong style={{ minWidth: '130px' }}>{r.concept}</strong>
                      <span style={{ color: 'var(--text-muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{r.question}</span>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      </div>

      {/* Interactive Study Session Card */}
      <div className="card">
        <h2>🎯 Adaptive Study Session</h2>
        <p>Learn target concepts guided by the agent. Understand core mechanisms before verifying your retention.</p>

        {stage === 'idle' && (
          <button onClick={startSession} disabled={loading || masteryEntries.length === 0} style={{ padding: '0.8rem 1.6rem', fontSize: '1rem' }}>
            {loading ? 'Preparing Material…' : '🚀 Explain Next Recommended Topic'}
          </button>
        )}

        {stage !== 'idle' && explanation && (
          <div className="explain-box">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontWeight: 700, color: 'var(--success-text)', fontSize: '0.9rem', marginBottom: '0.4rem' }}>
              <span>📖</span>
              <span>Concept Briefing: {explanation.decision?.concept || 'General Review'}</span>
            </div>
            <p>{explanation.explanation}</p>
            {explanation.sources && explanation.sources.length > 0 && (
              <details style={{ marginTop: '0.9rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                <summary style={{ cursor: 'pointer', fontWeight: 600 }}>
                  🔍 Grounded Source Evidence ({explanation.sources.length} passages via {explanation.sources[0]?.method || 'hybrid'} RAG)
                </summary>
                <div style={{ marginTop: '0.5rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  {explanation.sources.map((src) => (
                    <div key={src.chunk_index} style={{ background: '#FFFFFF', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid #DCFCE7' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: 'var(--success-text)', fontWeight: 600, marginBottom: '0.2rem' }}>
                        <span>Passage #{src.chunk_index + 1}</span>
                        <span>Relevance Score: {src.score}</span>
                      </div>
                      <div style={{ color: 'var(--text-main)', fontSize: '0.86rem' }}>{src.text}</div>
                    </div>
                  ))}
                </div>
              </details>
            )}
          </div>
        )}

        {stage === 'explained' && (
          <div style={{ marginTop: '1.25rem' }}>
            <p style={{ fontWeight: 600, color: 'var(--text-main)' }}>Ready to verify your understanding? Choose a test format:</p>
            <div className="choice-row">
              <button onClick={() => chooseTestType('mcq')} disabled={loading}>
                {loading ? 'Generating Questions…' : '📝 Multiple Choice Test (5 Qs)'}
              </button>
              <button className="secondary" onClick={() => chooseTestType('open')} disabled={loading}>
                ✍️ Written Synthesis Test
              </button>
            </div>
          </div>
        )}

        {(stage === 'quiz' || stage === 'result') && quiz && (
          <div className="quiz-box">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.8rem', flexWrap: 'wrap', gap: '0.4rem' }}>
              <span className="badge badge-primary">Question {qIndex + 1} of {questions.length}</span>
              {quiz.review && <span className="badge badge-warning">Review: {quiz.concept_name}</span>}
            </div>
            
            <p style={{ color: 'var(--text-main)', fontWeight: 600, fontSize: '1.05rem', margin: '0.5rem 0 1rem 0' }}>
              {quiz.question}
            </p>

            {stage === 'quiz' && (
              <>
                {isMcq ? quiz.options.map((opt) => (
                  <label key={opt} className={`mcq-option ${selected === opt ? 'selected' : ''}`}>
                    <input type="radio" name="mcq" checked={selected === opt} onChange={() => setSelected(opt)} />
                    <span>{opt}</span>
                  </label>
                )) : (
                  <div>
                    <textarea rows={4} placeholder="Explain the concept in your own words…" value={answer} onChange={(e) => setAnswer(e.target.value)} />
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-light)', marginTop: '0.3rem', display: 'block' }}>
                      Tip: Write a substantive explanation using your own words. Verbatim copying is automatically penalized.
                    </span>
                  </div>
                )}
                <div style={{ marginTop: '1.2rem' }}>
                  <button onClick={submit} disabled={loading || !canSubmit} style={{ padding: '0.75rem 1.6rem' }}>
                    {loading ? 'Evaluating with NLP…' : 'Submit for Grading'}
                  </button>
                </div>
              </>
            )}

            {stage === 'result' && evaluation && (
              <>
                <div className={`feedback-box ${evaluation.evaluation.score >= 6 ? 'good' : 'needs-work'}`}>
                  <div className="score-badge">
                    {isMcq ? (evaluation.evaluation.is_correct ? '✓ Correct' : '✗ Incorrect') : `${evaluation.evaluation.score}/10`}
                  </div>
                  <div>{evaluation.evaluation.feedback}</div>
                </div>
                <div style={{ marginTop: '1.25rem' }}>
                  <button onClick={nextQuestion} style={{ padding: '0.75rem 1.6rem' }}>
                    {lastQuestion ? 'View Final Results 🏆' : 'Next Question ➔'}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {stage === 'summary' && (
          <div className="quiz-box" style={{ textAlign: 'center', padding: '2.5rem 1.5rem' }}>
            <div style={{ fontSize: '3rem', marginBottom: '0.5rem' }}>
              {correctCount === questions.length ? '🎉' : correctCount / questions.length >= 0.6 ? '👏' : '📚'}
            </div>
            <h2>Assessment Complete!</h2>
            <p style={{ fontSize: '1.15rem', color: 'var(--text-main)', margin: '0.5rem 0 1rem 0' }}>
              You achieved <strong>{correctCount} out of {questions.length}</strong> correct
              {correctCount === questions.length ? ' — Outstanding mastery!' : correctCount / questions.length >= 0.6 ? ' — Solid understanding.' : ' — Recommended for revision.'}
            </p>
            <p style={{ maxWidth: '480px', margin: '0 auto 1.5rem auto', fontSize: '0.9rem' }}>
              Your knowledge graph and exponential mastery scores have been updated. The agent has revised its study plan based on these results.
            </p>
            <button onClick={resetSession} style={{ padding: '0.75rem 1.6rem' }}>Continue to Next Topic ➔</button>
          </div>
        )}
      </div>
    </div>
  )
}
