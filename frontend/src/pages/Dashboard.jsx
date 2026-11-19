import { useEffect, useState, useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { api } from '../api/client.js'

export default function Dashboard() {
  const { studentId } = useParams()
  const [profile, setProfile] = useState(null)
  const [decision, setDecision] = useState(null)
  const [progress, setProgress] = useState(null)
  const [error, setError] = useState(null)

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
      setError(err.status === 404
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
    setUploading(true); setUploadError(null); setUploadResult(null)
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
    try {
      setExplanation(await api.explain(studentId))
      setStage('explained')
    } catch (err) {
      setError('Could not start a study session.')
    } finally { setLoading(false) }
  }

  async function chooseTestType(type) {
    setLoading(true)
    try {
      const res = await api.test(studentId, type, 5)
      setQuestions(res.questions); setQIndex(0); setAnswers([])
      setAnswer(''); setSelected(''); setEvaluation(null)
      setStage('quiz')
    } catch (err) {
      setError('Could not generate the test.')
    } finally { setLoading(false) }
  }

  const quiz = questions[qIndex]
  const isMcq = quiz?.question_type === 'mcq'
  const canSubmit = isMcq ? !!selected : !!answer.trim()

  async function submit() {
    setLoading(true)
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
      setError('Could not submit your answer.')
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

  if (error) return <div className="shell"><p style={{ color: 'var(--alert)' }}>{error}</p></div>
  if (!profile) return <div className="shell"><p className="loading-text">Loading your profile…</p></div>

  const masteryEntries = Object.entries(profile.mastery || {})
  const correctCount = answers.filter(Boolean).length
  const lastQuestion = qIndex + 1 >= questions.length

  return (
    <div className="shell">
      <h1>Welcome back, {profile.name}</h1>
      <p>Subject: {profile.subject} · Goal: {profile.goal_score}%</p>

      {decision && (
        <div className="decision-card">
          <div className="label">What the agent decided</div>
          <strong>
            {decision.action === 'intervene' ? `Focus on: ${decision.concept}`
              : decision.action === 'review' ? `Time to review: ${decision.concept}`
              : 'Nothing to catch up on'}
          </strong>
          <p style={{ margin: '0.4em 0 0 0' }}>{decision.reasoning}</p>
        </div>
      )}

      <hr className="rule" />

      <h2>Your study material</h2>
      <p>Upload your notes or textbook (PDF). The agent builds your knowledge graph, explains it simply, and tests you.</p>
      <label htmlFor="material-upload" className="upload-drop">
        {uploading ? 'Reading your PDF and finding topics…' : 'Click to choose a PDF'}
      </label>
      {uploading && (
        <p style={{ fontSize: '0.85rem' }}>
          The first upload after the server starts also loads the language model, which can take a minute. Later uploads are quicker.
        </p>
      )}
      <input id="material-upload" type="file" accept="application/pdf"
        onChange={handleFileUpload} disabled={uploading} style={{ display: 'none' }} />
      {uploadError && <p style={{ color: 'var(--alert)' }}>{uploadError}</p>}
      {uploadResult && (
        <div className="decision-card" style={{ background: 'var(--growth-soft)', borderColor: '#B9D8CB' }}>
          <div className="label" style={{ color: 'var(--growth)' }}>
            Found {uploadResult.concepts_extracted.length} topics in {uploadResult.filename}
          </div>
          <p style={{ margin: '0.4em 0 0 0' }}>{uploadResult.concepts_extracted.join(' · ')}</p>
          {uploadResult.seconds && (
            <p style={{ margin: '0.5em 0 0 0', fontSize: '0.8rem' }}>
              Found in {uploadResult.seconds.total}s. Your notes are being indexed for search in the background.
            </p>
          )}
        </div>
      )}

      <hr className="rule" />

      <h2>Your progress</h2>
      {(!progress || progress.topics.length === 0) && <p>No topics yet. Upload a PDF above to get started.</p>}
      {progress && progress.topics.length > 0 && (
        <>
          <p style={{ color: 'var(--ink)' }}>
            {progress.summary.strong} of {progress.summary.total} topics strong
            {progress.summary.due > 0 && <> · <span className="tag-due">{progress.summary.due} due for review</span></>}
            {progress.summary.weak > 0 && <> · {progress.summary.weak} need practice</>}
            {progress.summary.new > 0 && <> · {progress.summary.new} not started</>}
          </p>
          {progress.topics.map((t) => (
            <div className="mastery-row" key={t.name}>
              <div className="mastery-name">
                {t.name}
                <div className={`mastery-status ${t.status === 'due' ? 'tag-due' : ''}`}>
                  {t.status === 'new' && 'Not started'}
                  {t.status === 'weak' && 'Needs more practice'}
                  {t.status === 'due' && `Due for review (practised ${t.days_since_practice} day(s) ago)`}
                  {t.status === 'scheduled' && (t.review_in_days === 0 ? 'Review due today' : `Next review in ${t.review_in_days} day(s)`)}
                </div>
              </div>
              <div className="mastery-bar-track">
                <div className={`mastery-bar-fill ${t.score < 60 ? 'weak' : ''}`} style={{ width: `${Math.min(t.score, 100)}%` }} />
              </div>
              <div className="mastery-pct">{Math.round(t.score)}%</div>
            </div>
          ))}
          {progress.recent.length > 0 && (
            <details style={{ marginTop: '1rem' }}>
              <summary style={{ cursor: 'pointer', fontSize: '0.9rem' }}>Recent activity ({progress.recent.length})</summary>
              {progress.recent.map((r, i) => (
                <p key={i} style={{ margin: '0.5em 0', fontSize: '0.85rem' }}>
                  <strong style={{ color: r.correct ? 'var(--growth)' : 'var(--alert)' }}>{r.correct ? 'Correct' : 'Incorrect'}</strong>
                  {' · '}{r.concept}: {r.question}
                </p>
              ))}
            </details>
          )}
        </>
      )}

      <hr className="rule" />

      <h2>Study session</h2>

      {stage === 'idle' && (
        <button onClick={startSession} disabled={loading || masteryEntries.length === 0}>
          {loading ? 'Preparing…' : 'Explain the next topic'}
        </button>
      )}

      {stage !== 'idle' && explanation && (
        <div className="explain-box">
          <div className="label" style={{ fontSize: '0.8rem', color: 'var(--growth)' }}>
            Let's learn: {explanation.decision.concept || 'general review'}
          </div>
          <p>{explanation.explanation}</p>
          {explanation.sources && explanation.sources.length > 0 && (
            <details style={{ marginTop: '0.8rem', fontSize: '0.85rem', color: 'var(--ink-soft)' }}>
              <summary style={{ cursor: 'pointer' }}>
                Retrieved from your notes ({explanation.sources.length} passages, {explanation.sources[0].method})
              </summary>
              {explanation.sources.map((src) => (
                <p key={src.chunk_index} style={{ margin: '0.6em 0', fontSize: '0.85rem' }}>
                  <strong>match {src.score}</strong>: {src.text}
                </p>
              ))}
            </details>
          )}
        </div>
      )}

      {stage === 'explained' && (
        <>
          <p style={{ marginTop: '1rem' }}>Ready to test yourself? Choose a format:</p>
          <div className="choice-row">
            <button onClick={() => chooseTestType('mcq')} disabled={loading}>
              {loading ? 'Building your test…' : 'Multiple choice test'}
            </button>
            <button className="secondary" onClick={() => chooseTestType('open')} disabled={loading}>Written test</button>
          </div>
        </>
      )}

      {(stage === 'quiz' || stage === 'result') && quiz && (
        <div className="quiz-box">
          <div style={{ fontSize: '0.8rem', color: 'var(--ink-soft)', marginBottom: '0.6rem' }}>
            Question {qIndex + 1} of {questions.length}
            {quiz.review && <span> · Review of a related topic: {quiz.concept_name}</span>}
          </div>
          <p style={{ color: 'var(--ink)', fontWeight: 500 }}>{quiz.question}</p>

          {stage === 'quiz' && (
            <>
              {isMcq ? quiz.options.map((opt) => (
                <label key={opt} className={`mcq-option ${selected === opt ? 'selected' : ''}`}>
                  <input type="radio" name="mcq" checked={selected === opt} onChange={() => setSelected(opt)} />
                  {opt}
                </label>
              )) : (
                <textarea rows={4} placeholder="Type your answer…" value={answer} onChange={(e) => setAnswer(e.target.value)} />
              )}
              <div style={{ marginTop: '0.8em' }}>
                <button onClick={submit} disabled={loading || !canSubmit}>{loading ? 'Checking…' : 'Submit answer'}</button>
              </div>
            </>
          )}

          {stage === 'result' && evaluation && (
            <>
              <div className={`feedback-box ${evaluation.evaluation.score >= 6 ? 'good' : 'needs-work'}`}>
                <div className="score-badge">{isMcq ? (evaluation.evaluation.is_correct ? 'Correct' : 'Incorrect') : `${evaluation.evaluation.score}/10`}</div>
                {evaluation.evaluation.feedback}
              </div>
              <div style={{ marginTop: '1em' }}>
                <button className="secondary" onClick={nextQuestion}>{lastQuestion ? 'See results' : 'Next question'}</button>
              </div>
            </>
          )}
        </div>
      )}

      {stage === 'summary' && (
        <div className="quiz-box">
          <h3>Test complete</h3>
          <p style={{ color: 'var(--ink)' }}>
            You got <strong>{correctCount} of {questions.length}</strong> correct
            {correctCount === questions.length ? ' — perfect.' : correctCount / questions.length >= 0.6 ? ' — good work.' : ' — this topic needs another pass.'}
          </p>
          <p>Your mastery bars above have been updated. The agent will pick your next topic based on them.</p>
          <button onClick={resetSession}>Next topic</button>
        </div>
      )}
    </div>
  )
}
