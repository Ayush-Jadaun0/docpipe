import { useEffect, useState } from 'react'
import { stats as getStats } from './api'
import { humanize } from './labels'

const SEG = [
  ['verified', 'Verified', 'var(--ok)'],
  ['corrected', 'Corrected', '#4f8f77'],
  ['unverified', 'Unverified', '#d99a00'],
  ['invalid', 'Invalid', 'var(--bad)'],
  ['missing', 'Not found', '#b7c0cc'],
]
const money = (a, cur) => `${cur ? cur + ' ' : ''}${a.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`

export default function Dashboard({ onOpen, onGo }) {
  const [s, setS] = useState(null)

  useEffect(() => {
    let on = true
    const load = () => getStats().then((d) => on && setS(d)).catch(() => {})
    load()
    const t = setInterval(load, 3000)
    return () => { on = false; clearInterval(t) }
  }, [])

  if (!s) return <p className="empty">Loading overview…</p>
  if (s.documents === 0) {
    return (
      <section className="intake">
        <h1>Nothing to show yet</h1>
        <p className="lede">The overview fills in as you process documents.</p>
        <button className="btn primary" onClick={() => onGo('documents')}>Upload your first document</button>
      </section>
    )
  }

  const fields = SEG.reduce((a, [k]) => a + (s.field_counts[k] || 0), 0)
  const maxDay = Math.max(1, ...s.per_day.map((d) => d.count))
  const maxType = Math.max(1, ...Object.values(s.by_type))
  const maxAmt = s.top_totals[0]?.amount || 1
  const passed = s.processed - s.needs_review

  return (
    <>
      <h1>Overview</h1>
      <p className="lede">
        {s.processed} of {s.documents} documents processed. {passed} passed every check and {s.needs_review} need review
        {s.failed ? `, ${s.failed} failed` : ''}{s.in_queue ? `. ${s.in_queue} still in the queue` : ''}.
      </p>

      {fields > 0 && (
        <section aria-label="Field quality">
          <h2>How far can you trust the extracted values?</h2>
          <div className="ribbon" role="img"
               aria-label={SEG.map(([k, l]) => `${l} ${s.field_counts[k] || 0}`).join(', ')}>
            {SEG.map(([k, , c]) => (s.field_counts[k] ? <span key={k} style={{ flexGrow: s.field_counts[k], background: c }} /> : null))}
          </div>
          <ul className="legend">
            {SEG.map(([k, l, c]) => (
              <li key={k}><i style={{ background: c }} />{l} <b>{s.field_counts[k] || 0}</b> ({Math.round(((s.field_counts[k] || 0) / fields) * 100)}%)</li>
            ))}
          </ul>
        </section>
      )}

      <dl className="facts">
        <div><dt>Average score</dt><dd>{s.avg_score ?? '–'}</dd></div>
        <div><dt>Average time per document</dt><dd>{s.avg_seconds != null ? `${s.avg_seconds} s` : '–'}</dd></div>
        <div><dt>Corrections saved</dt><dd>{s.corrections}</dd></div>
        <div><dt>Questions asked</dt><dd>{s.questions}</dd></div>
      </dl>

      <div className="cols">
        <section>
          <h2>Needs review</h2>
          {s.review_list.length === 0 ? <p className="empty">Nothing needs review right now.</p> : (
            <ul className="plain">
              {s.review_list.map((d) => (
                <li key={d.id}>
                  <button className="link" onClick={() => onOpen(d.id)}>{d.filename}</button>
                  <span className="muted">{humanize(d.doc_type)}, score {d.score}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
        <section>
          <h2>Largest totals</h2>
          {s.top_totals.length === 0 ? <p className="empty">No totals found yet.</p> : (
            <ul className="plain">
              {s.top_totals.map((t) => (
                <li key={t.id} className="amt">
                  <button className="link" onClick={() => onOpen(t.id)}>{t.filename}</button>
                  <b>{money(t.amount, t.currency)}</b>
                  <span className="hbar"><span style={{ width: `${(t.amount / maxAmt) * 100}%` }} /></span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="cols">
        <section>
          <h2>Documents in the last 7 days</h2>
          <div className="days">
            {s.per_day.map((d, i) => (
              <div key={i} className="day">
                <span className="n">{d.count}</span>
                <span className="col"><span style={{ height: `${(d.count / maxDay) * 100}%` }} /></span>
                <span className="l">{d.day}</span>
              </div>
            ))}
          </div>
        </section>
        <section>
          <h2>By document type</h2>
          <ul className="plain">
            {Object.entries(s.by_type).map(([t, n]) => (
              <li key={t} className="amt">
                <span>{humanize(t)}</span><b>{n}</b>
                <span className="hbar"><span style={{ width: `${(n / maxType) * 100}%` }} /></span>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </>
  )
}
