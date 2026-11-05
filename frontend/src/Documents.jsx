import { useEffect, useMemo, useState } from 'react'
import { deleteJob, docTypes, exportUrl, upload } from './api'
import { STAGES, humanize } from './labels'

function Status({ job }) {
  if (job.status === 'failed') return <span className="tone-bad">Failed: {job.error}</span>
  if (job.status === 'done') {
    return job.needs_review ? <span className="pill warn">Needs review</span> : <span className="pill ok">Looks good</span>
  }
  const label = STAGES[job.stage] || job.stage
  return (
    <div className="progress">
      <div className="bar" role="progressbar" aria-label={label} aria-valuenow={job.progress} aria-valuemin="0" aria-valuemax="100">
        <span style={{ width: `${job.progress}%` }} />
      </div>
      <small>{label}</small>
    </div>
  )
}

const matchStatus = (j, f) =>
  !f ||
  (f === 'review' && j.status === 'done' && j.needs_review) ||
  (f === 'good' && j.status === 'done' && !j.needs_review) ||
  (f === 'working' && (j.status === 'queued' || j.status === 'processing')) ||
  (f === 'failed' && j.status === 'failed')

export default function Documents({ jobs, onOpen, onUploaded }) {
  const [types, setTypes] = useState({})
  const [docType, setDocType] = useState('')
  const [busy, setBusy] = useState(false)
  const [msg, setMsg] = useState('')
  const [over, setOver] = useState(false)
  const [q, setQ] = useState('')
  const [typeF, setTypeF] = useState('')
  const [statusF, setStatusF] = useState('')
  const [picked, setPicked] = useState(new Set())

  useEffect(() => { docTypes().then(setTypes).catch(() => {}) }, [])

  async function send(fileList) {
    const files = [...fileList]
    if (!files.length) return
    setBusy(true)
    setMsg('')
    try {
      await upload(files, docType)
      onUploaded()
    } catch (e) {
      setMsg(e.message)
    } finally {
      setBusy(false)
    }
  }

  const shown = useMemo(
    () => jobs.filter((j) => (!q || j.filename.toLowerCase().includes(q.toLowerCase())) && (!typeF || j.doc_type === typeF) && matchStatus(j, statusF)),
    [jobs, q, typeF, statusF],
  )
  const doneShown = shown.filter((j) => j.status === 'done')
  const allPicked = doneShown.length > 0 && doneShown.every((j) => picked.has(j.id))
  async function remove(ids) {
    const what = ids.length === 1 ? 'this document' : `these ${ids.length} documents`
    if (!window.confirm(`Delete ${what}? The file, its extracted data, answers and corrections will be removed. This cannot be undone.`)) return
    setMsg('')
    const results = await Promise.allSettled(ids.map(deleteJob))
    const failed = results.find((r) => r.status === 'rejected')
    if (failed) setMsg(failed.reason.message)
    setPicked((p) => { const n = new Set(p); ids.forEach((id) => n.delete(id)); return n })
    onUploaded()
  }
  const toggle = (id) => setPicked((p) => { const n = new Set(p); n.has(id) ? n.delete(id) : n.add(id); return n })
  const toggleAll = () => setPicked(allPicked ? new Set() : new Set(doneShown.map((j) => j.id)))

  return (
    <>
      <section className="intake">
        <h1>Check what your documents say</h1>
        <p className="lede">Upload invoices, receipts, IDs or resumes. Every extracted value is checked against the document before you see it, and you can ask questions about each file.</p>
        <div className="intake-row">
          <label className={`drop${over ? ' over' : ''}`}
                 onDragOver={(e) => { e.preventDefault(); setOver(true) }}
                 onDragLeave={() => setOver(false)}
                 onDrop={(e) => { e.preventDefault(); setOver(false); send(e.dataTransfer.files) }}>
            <input type="file" multiple accept=".pdf,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
                   onChange={(e) => { send(e.target.files); e.target.value = '' }} />
            <strong>{busy ? 'Uploading…' : 'Drop files here or choose files'}</strong>
            <span>PDF, PNG or JPG, up to 20 MB each</span>
          </label>
          <div className="field-row">
            <label htmlFor="dt">Document type</label>
            <select id="dt" value={docType} onChange={(e) => setDocType(e.target.value)}>
              <option value="">Detect automatically</option>
              {Object.keys(types).map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </select>
          </div>
        </div>
        {msg && <p className="notice bad" role="alert">{msg}</p>}
      </section>

      <section>
        <div className="list-head">
          <h2>Documents</h2>
          <div className="filters">
            <input type="search" aria-label="Search by file name" placeholder="Search by file name" value={q} onChange={(e) => setQ(e.target.value)} />
            <select aria-label="Filter by type" value={typeF} onChange={(e) => setTypeF(e.target.value)}>
              <option value="">All types</option>
              {Object.keys(types).map((t) => <option key={t} value={t}>{humanize(t)}</option>)}
            </select>
            <select aria-label="Filter by status" value={statusF} onChange={(e) => setStatusF(e.target.value)}>
              <option value="">Any status</option>
              <option value="review">Needs review</option>
              <option value="good">Looks good</option>
              <option value="working">In progress</option>
              <option value="failed">Failed</option>
            </select>
            {picked.size > 0 && <a className="btn" href={exportUrl([...picked])} download>Export {picked.size} selected</a>}
            {picked.size > 0 && <button className="btn danger" onClick={() => remove([...picked])}>Delete {picked.size} selected</button>}
          </div>
        </div>
        {jobs.length === 0 ? (
          <p className="empty">Nothing here yet. Drop a PDF, PNG or JPG above to start.</p>
        ) : shown.length === 0 ? (
          <p className="empty">No documents match these filters.</p>
        ) : (
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th><input type="checkbox" aria-label="Select all finished documents" checked={allPicked} onChange={toggleAll} /></th>
                  <th>File</th><th>Type</th><th>Progress</th><th className="num">Score</th><th><span className="sr">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {shown.map((j) => (
                  <tr key={j.id}>
                    <td>{j.status === 'done' && <input type="checkbox" aria-label={`Select ${j.filename}`} checked={picked.has(j.id)} onChange={() => toggle(j.id)} />}</td>
                    <td className="file">{j.filename}</td>
                    <td>{j.doc_type ? humanize(j.doc_type) : '–'}</td>
                    <td><Status job={j} /></td>
                    <td className="num">{j.score ?? ''}</td>
                    <td className="actions">
                      {j.status === 'done' && <button className="btn" onClick={() => onOpen(j.id)}>Open</button>}
                      {(j.status === 'done' || j.status === 'failed') && (
                        <button className="btn danger" aria-label={`Delete ${j.filename}`} onClick={() => remove([j.id])}>Delete</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}
