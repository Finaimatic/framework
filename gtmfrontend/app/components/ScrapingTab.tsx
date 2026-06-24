'use client'

import { useEffect, useRef, useState, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'

const inp = 'px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500'

interface Stats {
  total_leads: number
  unique_domains: number
  scraped_ok: number
  scraped_failed: number
}

interface ListSummary { id: number; name: string; entry_count: number }

interface Job {
  id: string
  status: string
  log: string[]
  started_at: string
  finished_at: string | null
  exit_code: number | null
}

function StatPill({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-slate-700 bg-slate-800 px-6 py-4 min-w-[130px]">
      <span className="text-2xl font-bold text-slate-100">{typeof value === 'number' ? value.toLocaleString() : value}</span>
      <span className="text-slate-500 text-xs mt-1">{label}</span>
    </div>
  )
}

export function ScrapingTab() {
  const [stats, setStats]       = useState<Stats | null>(null)
  const [listId, setListId]     = useState<string>('')
  const [lists, setLists]       = useState<ListSummary[]>([])
  const [limit, setLimit]       = useState('')
  const [domain, setDomain]     = useState('')
  const [workers, setWorkers]   = useState('5')
  const [allMode, setAllMode]   = useState(false)
  const [jobId, setJobId]       = useState<string | null>(null)
  const [job, setJob]           = useState<Job | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  const loadStats = useCallback(() => {
    fetch(`${API}/scraping/stats`)
      .then(r => r.json()).then(setStats).catch(() => {})
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  useEffect(() => {
    fetch(`${API}/lists`).then(r => r.json()).then(setLists).catch(() => {})
  }, [])

  useEffect(() => {
    if (!jobId) return
    const poll = setInterval(() => {
      fetch(`${API}/scraping/job/${jobId}`)
        .then(r => r.json())
        .then((j: Job) => {
          setJob(j)
          if (j.status === 'done') {
            clearInterval(poll)
            loadStats()
          }
        })
        .catch(() => clearInterval(poll))
    }, 1500)
    return () => clearInterval(poll)
  }, [jobId, loadStats])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [job?.log.length])

  const run = async () => {
    setJob(null)
    const res = await fetch(`${API}/scraping/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        list_id: listId ? Number(listId) : null,
        limit: limit ? Number(limit) : null,
        domain: domain || null,
        all_mode: allMode,
        workers: workers ? Number(workers) : 5,
      }),
    })
    if (!res.ok) return
    const { job_id } = await res.json() as { job_id: string }
    setJobId(job_id)
  }

  const running = job?.status === 'running'
  const pctScraped = stats && stats.unique_domains > 0
    ? Math.round(stats.scraped_ok / stats.unique_domains * 100)
    : 0

  return (
    <div className="space-y-6">
      {/* Stats */}
      <div className="flex gap-4 flex-wrap">
        <StatPill label="Total Leads" value={stats?.total_leads ?? '—'} />
        <StatPill label="Unique Domains" value={stats?.unique_domains ?? '—'} />
        <StatPill label="Scraped OK" value={stats?.scraped_ok ?? '—'} />
        {(stats?.scraped_failed ?? 0) > 0 && (
          <StatPill label="Failed" value={stats!.scraped_failed} />
        )}
        {stats && stats.unique_domains > 0 && (
          <div className="flex flex-col justify-center rounded-xl border border-slate-700 bg-slate-800 px-6 py-4 min-w-[160px]">
            <div className="flex items-end gap-1 mb-1.5">
              <span className="text-2xl font-bold text-slate-100">{pctScraped}%</span>
              <span className="text-slate-500 text-xs mb-0.5">scraped</span>
            </div>
            <div className="w-full h-1.5 rounded-full bg-slate-700 overflow-hidden">
              <div
                className="h-full rounded-full bg-indigo-500 transition-all"
                style={{ width: `${pctScraped}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Run Panel */}
      <div className="rounded-xl border border-slate-700 bg-slate-800 p-5 space-y-4">
        <span className="text-slate-300 text-sm font-semibold">Run Scraper</span>

        <div className="flex flex-wrap gap-3 items-end">
          <div className="flex flex-col gap-1">
            <label className="text-slate-500 text-xs">List</label>
            <select value={listId} onChange={e => setListId(e.target.value)}
              className={inp + ' w-44'}>
              <option value="">All leads</option>
              {lists.map(l => (
                <option key={l.id} value={String(l.id)}>{l.name} ({l.entry_count})</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-slate-500 text-xs">Limit</label>
            <input type="number" placeholder="all" value={limit}
              onChange={e => setLimit(e.target.value)}
              className={inp + ' w-24'} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-slate-500 text-xs">Domain filter</label>
            <input type="text" placeholder="e.g. acme.com" value={domain}
              onChange={e => setDomain(e.target.value)}
              className={inp + ' w-44'} />
          </div>
          <div className="flex flex-col gap-1">
            <label className="text-slate-500 text-xs">Workers</label>
            <input type="number" value={workers} min={1} max={20}
              onChange={e => setWorkers(e.target.value)}
              className={inp + ' w-20'} />
          </div>
          <label className="flex items-center gap-2 text-slate-400 text-sm cursor-pointer pb-1">
            <input type="checkbox" checked={allMode} onChange={e => setAllMode(e.target.checked)}
              className="accent-indigo-500" />
            Re-scrape all
          </label>
          <button onClick={run} disabled={running}
            className="px-5 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-40 transition-colors">
            {running ? 'Running…' : 'Run'}
          </button>
        </div>

        {/* Log */}
        {job && (
          <div className="space-y-1.5">
            <div className="flex items-center gap-2">
              <span className={`text-xs font-medium ${
                job.status === 'running' ? 'text-amber-400' :
                job.exit_code === 0 ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {job.status === 'running' ? '● running' : job.exit_code === 0 ? '✓ done' : `✗ exit ${job.exit_code}`}
              </span>
              {job.finished_at && (
                <span className="text-slate-600 text-xs">
                  {new Date(job.finished_at).toLocaleTimeString()}
                </span>
              )}
            </div>
            <div ref={logRef}
              className="h-80 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-400 space-y-0.5">
              {job.log.map((line, i) => (
                <div key={i} className={
                  line.includes('FAIL') || line.includes('[launcher error]') ? 'text-red-400' :
                  line.includes(' OK ') ? 'text-emerald-400' :
                  line.startsWith('Scraping') || line.startsWith('Done.') || line.startsWith('List:') || line.startsWith('To scrape:') ? 'text-indigo-300' : ''
                }>{line || ' '}</div>
              ))}
              {running && <div className="text-slate-600 animate-pulse">…</div>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
