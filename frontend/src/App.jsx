import { useCallback, useEffect, useState } from 'react'
import { exportUrl, listJobs } from './api'
import AskAll from './AskAll.jsx'
import Dashboard from './Dashboard.jsx'
import Documents from './Documents.jsx'
import Review from './Review.jsx'

const TABS = [['dashboard', 'Dashboard'], ['documents', 'Documents'], ['ask', 'Ask all documents']]

export default function App() {
  const [tab, setTab] = useState('documents')
  const [openId, setOpenId] = useState(null)
  const [jobs, setJobs] = useState([])
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    try {
      setJobs(await listJobs())
      setError('')
    } catch {
      setError("Can't reach the backend. Start it in another terminal with: uvicorn server:app --reload")
    }
  }, [])

  useEffect(() => {
    refresh()
    const t = setInterval(refresh, 1500)
    return () => clearInterval(t)
  }, [refresh])

  const go = (t) => { setOpenId(null); setTab(t) }

  return (
    <>
      <header className="top">
        <button className="brand" onClick={() => go('dashboard')}>DocPipe</button>
        <nav aria-label="Main">
          {TABS.map(([k, label]) => {
            const on = !openId && tab === k
            return (
              <button key={k} className={`nav${on ? ' on' : ''}`} aria-current={on ? 'page' : undefined} onClick={() => go(k)}>
                {label}
              </button>
            )
          })}
        </nav>
        <a className="btn ghost" href={exportUrl()} download>Export all to CSV</a>
      </header>
      <main>
        {error && <p className="notice bad" role="alert">{error}</p>}
        {openId ? (
          <Review id={openId} onBack={() => setOpenId(null)} />
        ) : tab === 'dashboard' ? (
          <Dashboard onOpen={setOpenId} onGo={go} />
        ) : tab === 'ask' ? (
          <AskAll onOpen={setOpenId} />
        ) : (
          <Documents jobs={jobs} onOpen={setOpenId} onUploaded={refresh} />
        )}
      </main>
    </>
  )
}
