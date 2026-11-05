async function parse(r) {
  if (!r.ok) {
    let msg = r.statusText
    try {
      const b = await r.json()
      msg = typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail)
    } catch {}
    throw new Error(msg)
  }
  return r.json()
}
const post = (url, body) =>
  fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) }).then(parse)

export const listJobs = () => fetch('/api/jobs').then(parse)
export const getJob = (id) => fetch(`/api/jobs/${id}`).then(parse)
export const docTypes = () => fetch('/api/doc-types').then(parse)
export const stats = () => fetch('/api/stats').then(parse)
export const qaHistory = (id) => fetch(`/api/jobs/${id}/qa`).then(parse)
export const askDoc = (id, question) => post(`/api/jobs/${id}/ask`, { question })
export const askAll = (question) => post('/api/ask', { question })

export function upload(files, docType) {
  const fd = new FormData()
  files.forEach((f) => fd.append('files', f))
  fd.append('doc_type', docType || '')
  return fetch('/api/upload', { method: 'POST', body: fd }).then(parse)
}

export const correct = (id, name, value) =>
  fetch(`/api/jobs/${id}/fields/${encodeURIComponent(name)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ value }),
  }).then(parse)

export const pageUrl = (id, n) => `/api/jobs/${id}/pages/${n}`
export const exportUrl = (ids) => (ids && ids.length ? `/api/export.csv?ids=${ids.join(',')}` : '/api/export.csv')

export const deleteJob = (id) => fetch(`/api/jobs/${id}`, { method: 'DELETE' }).then(parse)
