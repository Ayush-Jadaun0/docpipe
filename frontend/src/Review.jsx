import { useEffect, useRef, useState } from 'react'
import { correct, deleteJob, getJob, pageUrl } from './api'
import Ask from './Ask.jsx'
import { STATUS, SUGGEST, humanize } from './labels'

function Mark({ status }) {
  const s = STATUS[status] || STATUS.missing
  return <span className={`mark-badge ${s.tone}`}><span aria-hidden="true">{s.icon}</span> {s.label}</span>
}

export default function Review({ id, onBack }) {
  const [job, setJob] = useState(null)
  const [err, setErr] = useState('')
  const [tab, setTab] = useState('ask')
  const [sel, setSel] = useState(null)
  const [page, setPage] = useState(1)
  const [mark, setMark] = useState(null)
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const markRef = useRef(null)

  useEffect(() => { getJob(id).then(setJob).catch((e) => setErr(e.message)) }, [id])
  useEffect(() => { markRef.current?.scrollIntoView({ block: 'center' }) }, [mark, page])

  const res = job?.result
  if (err && !res) return <p className="notice bad" role="alert">{err} <button className="btn ghost" onClick={onBack}>Back to documents</button></p>
  if (!res) return <p className="empty">Loading document…</p>

  const field = res.fields.find((f) => f.name === sel)
  const pg = res.pages[page - 1]
  const attention = res.counts.invalid + res.counts.unverified
  const changed = field ? draft.trim() !== String(field.value ?? '') : false
  const b = mark && mark.page === page && pg ? mark.bbox : null

  function pick(f) {
    setSel(f.name)
    setDraft(String(f.value ?? ''))
    setErr('')
    if (f.page) setPage(f.page)
    setMark(f.bbox && f.page ? { page: f.page, bbox: f.bbox } : null)
  }

  function showSource(src) {
    if (src.page) setPage(src.page)
    setMark(src.bbox ? { page: src.page, bbox: src.bbox } : null)
  }

  async function removeDoc() {
    if (!window.confirm('Delete this document? The file, its extracted data, answers and corrections will be removed. This cannot be undone.')) return
    try { await deleteJob(id); onBack() }
    catch (e) { setErr(e.message) }
  }

  async function save() {
    setSaving(true)
    try { setJob(await correct(id, field.name, draft)); setErr('') }
    catch (e) { setErr(e.message) }
    finally { setSaving(false) }
  }

  return (
    <>
      <div className="review-head">
        <button className="btn ghost" onClick={onBack}>All documents</button>
        <div>
          <h1>{job.filename}</h1>
          <p className="lede">
            {humanize(res.doc_type)}, score {res.score} out of 100.{' '}
            {attention ? `${attention} ${attention === 1 ? 'field needs' : 'fields need'} a look.` : 'Every field found has been checked.'}
          </p>
        </div>
        <button className="btn danger push" onClick={removeDoc}>Delete document</button>
      </div>

      <div className="review">
        <section aria-label="Document page">
          {res.pages.length > 1 && (
            <div className="pager">
              {res.pages.map((p) => (
                <button key={p.number} className={`btn ghost${p.number === page ? ' on' : ''}`}
                        aria-pressed={p.number === page} onClick={() => setPage(p.number)}>Page {p.number}</button>
              ))}
            </div>
          )}
          <div className="sheet">
            <img src={pageUrl(id, page)} alt={`Page ${page} of ${job.filename}`} />
            {b && (
              <div ref={markRef} className="highlight" aria-hidden="true"
                   style={{ left: `${(b[0] / pg.width) * 100}%`, top: `${(b[1] / pg.height) * 100}%`,
                            width: `${((b[2] - b[0]) / pg.width) * 100}%`, height: `${((b[3] - b[1]) / pg.height) * 100}%` }} />
            )}
          </div>
        </section>

        <section aria-label="Document tools">
          <div className="tabs" role="tablist">
            {[['ask', 'Ask questions'], ['fields', 'Extracted fields']].map(([k, label]) => (
              <button key={k} role="tab" aria-selected={tab === k} className={`tab${tab === k ? ' on' : ''}`} onClick={() => setTab(k)}>{label}</button>
            ))}
          </div>

          <div role="tabpanel" hidden={tab !== 'ask'}>
            <Ask jobId={id} suggestions={SUGGEST[res.doc_type] || SUGGEST.other} onSource={showSource} />
          </div>

          <div role="tabpanel" hidden={tab !== 'fields'}>
            {err && <p className="notice bad" role="alert">{err}</p>}
            <ul className="fields">
              {res.fields.map((f) => {
                const open = f.name === sel
                return (
                  <li key={f.name} className={`row ${STATUS[f.status]?.tone || 'mute'}${open ? ' open' : ''}`}>
                    <button className="row-btn" aria-expanded={open} onClick={() => pick(f)}>
                      <span className="row-label">{humanize(f.name)}</span>
                      <span className={`row-value${f.value == null ? ' none' : ''}`}>{f.value ?? 'Not found'}</span>
                      <Mark status={f.status} />
                    </button>
                    {open && (
                      <div className="editor">
                        {f.reasons?.length > 0 && <p className="why">{f.reasons.join('. ')}.</p>}
                        {f.value != null && !f.bbox && <p className="why">This value could not be located on the page, so nothing is highlighted.</p>}
                        <label htmlFor="edit">Value</label>
                        <input id="edit" value={draft} onChange={(e) => setDraft(e.target.value)}
                               onKeyDown={(e) => { if (e.key === 'Enter' && (changed || f.value != null)) save() }} />
                        <button className="btn primary" disabled={saving || (!changed && f.value == null)} onClick={save}>
                          {saving ? 'Saving…' : changed ? 'Save correction' : 'Confirm value'}
                        </button>
                      </div>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        </section>
      </div>
    </>
  )
}
