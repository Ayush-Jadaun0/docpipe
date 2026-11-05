import { useEffect, useRef, useState } from 'react'
import { askAll, askDoc, qaHistory } from './api'

// jobId set: questions about one document. jobId empty: questions across all documents.
export default function Ask({ jobId, suggestions = [], onSource, onOpenDoc }) {
  const [items, setItems] = useState([])
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef(null)

  useEffect(() => { if (jobId) qaHistory(jobId).then(setItems).catch(() => {}) }, [jobId])
  useEffect(() => { end.current?.scrollIntoView({ block: 'nearest' }) }, [items.length, busy])

  async function submit(q) {
    const question = (q ?? text).trim()
    if (question.length < 2 || busy) return
    setText('')
    setBusy(true)
    setItems((i) => [...i, { question, pending: true }])
    try {
      const a = jobId ? await askDoc(jobId, question) : await askAll(question)
      setItems((i) => [...i.slice(0, -1), a])
    } catch (e) {
      setItems((i) => [...i.slice(0, -1), { question, error: e.message }])
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ask">
      <div className="thread" aria-live="polite">
        {items.length === 0 && (
          <div className="starters">
            <p className="muted">{jobId ? 'Ask anything about this document. Answers point to the exact place they came from.' : 'Ask about all your documents at once.'}</p>
            <div className="chips">
              {suggestions.map((s) => <button key={s} className="chip" onClick={() => submit(s)}>{s}</button>)}
            </div>
          </div>
        )}
        {items.map((it, i) => (
          <article key={i} className="turn">
            <p className="q">{it.question}</p>
            {it.pending && <p className="muted">Reading {jobId ? 'the document' : 'your documents'}…</p>}
            {it.error && <p className="notice bad" role="alert">{it.error}</p>}
            {it.answer && (
              <>
                <p className="answer">{it.answer}</p>
                {jobId && it.found && (
                  <div className="source">
                    {it.quote && <blockquote>{it.quote}</blockquote>}
                    <div className="source-row">
                      {it.verified
                        ? <span className="mark-badge ok">✓ Source found in the document</span>
                        : <span className="mark-badge bad">! Source not found in the document</span>}
                      {it.page && <button className="btn ghost small" onClick={() => onSource({ page: it.page, bbox: it.bbox })}>Show on page {it.page}</button>}
                    </div>
                  </div>
                )}
                {!jobId && it.sources?.length > 0 && (
                  <div className="chips">
                    {it.sources.map((s) => (
                      <button key={s.doc} className="chip" onClick={() => onOpenDoc(s.doc)}>{s.filename}{s.page ? `, page ${s.page}` : ''}</button>
                    ))}
                  </div>
                )}
                {!jobId && <p className="muted small">Searched {it.searched} of {it.total} documents{it.truncated ? '. Older documents were left out.' : '.'}</p>}
                {it.warnings?.map((w) => <p key={w} className="why warn-text">{w}</p>)}
              </>
            )}
          </article>
        ))}
        <div ref={end} />
      </div>
      <form className="askbar" onSubmit={(e) => { e.preventDefault(); submit() }}>
        <input aria-label="Your question" placeholder={jobId ? 'Ask about this document' : 'Ask about all documents'}
               value={text} onChange={(e) => setText(e.target.value)} maxLength={500} />
        <button className="btn primary" disabled={busy || text.trim().length < 2}>{busy ? 'Asking…' : 'Ask'}</button>
      </form>
    </div>
  )
}
