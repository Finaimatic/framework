'use client'

import { useEffect, useRef, useState, useCallback } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
} from '@tanstack/react-table'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'

const inp = 'px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500'

interface ScoredLead {
  id: number
  full_name: string | null
  title: string | null
  company_name: string | null
  lead_country: string | null
  fit_score: number | null
  tier: string | null
  confidence: string | null
  disqualified: number | null
  disqualifier: string | null
  score_reason: string | null
  scored_at: string | null
}

interface ScoredLeadsResponse {
  total: number; page: number; pages: number
  results: ScoredLead[]
}

interface Job {
  id: string; status: string; spec: string
  log: string[]; started_at: string; finished_at: string | null; exit_code: number | null
}

interface ListSummary { id: number; name: string; entry_count: number }

// ─── Spec Editor ──────────────────────────────────────────────────────────────

function SpecEditor({ onSpecsChange }: { onSpecsChange: (specs: string[]) => void }) {
  const [specs, setSpecs]       = useState<string[]>([])
  const [active, setActive]     = useState<string | null>(null)
  const [content, setContent]   = useState('')
  const [newName, setNewName]   = useState('')
  const [creating, setCreating] = useState(false)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')

  const loadSpecs = useCallback(() => {
    fetch(`${API}/scoring/specs`).then(r => r.json()).then((s: string[]) => {
      setSpecs(s)
      onSpecsChange(s)
    }).catch(() => {})
  }, [onSpecsChange])

  useEffect(() => { loadSpecs() }, [loadSpecs])

  const selectSpec = (name: string) => {
    setActive(name)
    setCreating(false)
    setError('')
    fetch(`${API}/scoring/specs/${name}`)
      .then(r => r.json())
      .then((d: { content: string }) => setContent(d.content))
      .catch(() => setError('Failed to load spec'))
  }

  const save = async () => {
    if (!active && !creating) return
    setSaving(true); setError('')
    try {
      if (creating) {
        const name = newName.endsWith('.yaml') ? newName : `${newName}.yaml`
        const res = await fetch(`${API}/scoring/specs`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name, content }),
        })
        if (!res.ok) { setError(await res.text()); return }
        setCreating(false); setNewName(''); setActive(name); loadSpecs()
      } else {
        const res = await fetch(`${API}/scoring/specs/${active}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content }),
        })
        if (!res.ok) { setError(await res.text()); return }
      }
    } finally { setSaving(false) }
  }

  const del = async () => {
    if (!active) return
    if (!confirm(`Delete ${active}?`)) return
    await fetch(`${API}/scoring/specs/${active}`, { method: 'DELETE' })
    setActive(null); setContent(''); loadSpecs()
  }

  const startCreate = () => {
    setCreating(true); setActive(null)
    setContent(TEMPLATE); setNewName(''); setError('')
  }

  return (
    <div className="flex flex-col h-full gap-3">
      <div className="flex items-center gap-2">
        <span className="text-slate-300 text-sm font-semibold flex-1">ICP Specs</span>
        <button onClick={startCreate}
          className="px-2.5 py-1 rounded-lg border border-slate-600 text-slate-300 text-xs hover:bg-slate-700 transition-colors">
          + New
        </button>
      </div>
      <div className="space-y-1">
        {specs.map(s => (
          <button key={s} onClick={() => selectSpec(s)}
            className={`w-full text-left px-3 py-2 rounded-lg text-xs transition-colors truncate ${
              active === s && !creating
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/40'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}>
            {s}
          </button>
        ))}
        {specs.length === 0 && !creating && (
          <p className="text-slate-600 text-xs px-2">No specs yet. Create one.</p>
        )}
      </div>
      {(active || creating) && (
        <div className="flex flex-col gap-2 flex-1">
          {creating && (
            <input type="text" placeholder="filename.yaml" value={newName}
              onChange={e => setNewName(e.target.value)}
              className={inp + ' text-xs'} />
          )}
          <textarea
            value={content}
            onChange={e => setContent(e.target.value)}
            spellCheck={false}
            className="flex-1 min-h-56 px-3 py-2 rounded-lg border border-slate-600 bg-slate-900 text-slate-200 text-xs font-mono resize-none focus:outline-none focus:border-indigo-500"
          />
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <div className="flex gap-2">
            <button onClick={save} disabled={saving}
              className="flex-1 py-1.5 rounded-lg bg-indigo-600 text-white text-xs font-medium hover:bg-indigo-500 disabled:opacity-40 transition-colors">
              {saving ? 'Saving...' : 'Save'}
            </button>
            {active && !creating && (
              <button onClick={del}
                className="px-3 py-1.5 rounded-lg border border-red-800/60 text-red-400/70 text-xs hover:text-red-300 hover:bg-red-900/20 transition-colors">
                Delete
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Run Panel ────────────────────────────────────────────────────────────────

function RunPanel({ specs, onDone }: { specs: string[]; onDone: () => void }) {
  const [spec, setSpec]       = useState('')
  const [listId, setListId]   = useState<string>('')
  const [lists, setLists]     = useState<ListSummary[]>([])
  const [limit, setLimit]     = useState('')
  const [allMode, setAllMode] = useState(true)
  const [jobId, setJobId]     = useState<string | null>(null)
  const [job, setJob]         = useState<Job | null>(null)
  const logRef = useRef<HTMLDivElement>(null)

  useEffect(() => { if (specs.length && !spec) setSpec(specs[0]) }, [specs, spec])

  useEffect(() => {
    fetch(`${API}/lists`).then(r => r.json()).then(setLists).catch(() => {})
  }, [])

  useEffect(() => {
    if (!jobId) return
    const poll = setInterval(() => {
      fetch(`${API}/scoring/job/${jobId}`)
        .then(r => r.json())
        .then((j: Job) => {
          setJob(j)
          if (j.status === 'done') { clearInterval(poll); onDone() }
        })
        .catch(() => clearInterval(poll))
    }, 1500)
    return () => clearInterval(poll)
  }, [jobId, onDone])

  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight
  }, [job?.log.length])

  const run = async () => {
    if (!spec) return
    setJob(null)
    const res = await fetch(`${API}/scoring/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        spec,
        list_id: listId ? Number(listId) : null,
        limit: limit ? Number(limit) : null,
        all_mode: allMode,
      }),
    })
    if (!res.ok) return
    const { job_id } = await res.json() as { job_id: string }
    setJobId(job_id)
  }

  const running = job?.status === 'running'

  return (
    <div className="flex flex-col gap-3 h-full">
      <span className="text-slate-300 text-sm font-semibold">Run Scoring</span>

      <div className="flex flex-wrap gap-2 items-end">
        <div className="flex flex-col gap-1">
          <label className="text-slate-500 text-xs">Spec</label>
          <select value={spec} onChange={e => setSpec(e.target.value)}
            className={inp + ' w-44'}>
            {specs.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
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
            className={inp + ' w-20'} />
        </div>
        <label className="flex items-center gap-2 text-slate-400 text-sm cursor-pointer">
          <input type="checkbox" checked={allMode} onChange={e => setAllMode(e.target.checked)}
            className="accent-indigo-500" />
          Re-score all
        </label>
        <button onClick={run} disabled={!spec || running}
          className="px-4 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-40 transition-colors">
          {running ? 'Running...' : 'Run'}
        </button>
      </div>

      {job && (
        <div className="flex-1 flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <span className={`text-xs font-medium ${
              job.status === 'done' && job.exit_code === 0 ? 'text-emerald-400' :
              job.status === 'done' ? 'text-red-400' : 'text-amber-400'
            }`}>
              {job.status === 'running' ? '● running' : job.exit_code === 0 ? '✓ done' : `✗ exit ${job.exit_code}`}
            </span>
            <span className="text-slate-600 text-xs">{job.spec}</span>
          </div>
          <div ref={logRef}
            className="flex-1 min-h-40 max-h-72 overflow-y-auto rounded-lg border border-slate-700 bg-slate-950 p-3 font-mono text-xs text-slate-400 space-y-0.5">
            {job.log.map((line, i) => (
              <div key={i} className={
                line.startsWith('[error]') || line.startsWith('ERROR') ? 'text-red-400' :
                line.includes('score=') ? 'text-emerald-400' :
                line.startsWith('To score') || line.startsWith('List:') ? 'text-indigo-300' : ''
              }>{line || ' '}</div>
            ))}
            {running && <div className="text-slate-600 animate-pulse">...</div>}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Results Table ────────────────────────────────────────────────────────────

const TIER_COLOURS: Record<string, string> = {
  A: 'text-emerald-400', B: 'text-indigo-300', C: 'text-amber-400',
  D: 'text-slate-500', skip: 'text-slate-600',
}

const RESULTS_COLS: ColumnDef<ScoredLead, unknown>[] = [
  { id: 'full_name', header: 'Name',
    cell: ({ row: { original: r } }) => <span className="text-slate-200 text-xs">{r.full_name || '—'}</span> },
  { id: 'title', header: 'Title',
    cell: ({ row: { original: r } }) => <span className="text-slate-400 text-xs">{r.title || '—'}</span> },
  { id: 'company_name', header: 'Company',
    cell: ({ row: { original: r } }) => <span className="text-slate-200 text-xs">{r.company_name || '—'}</span> },
  { id: 'fit_score', header: 'Score',
    cell: ({ row: { original: r } }) => (
      <span className={`text-xs font-semibold ${r.fit_score != null && r.fit_score >= 7 ? 'text-emerald-400' : r.fit_score != null && r.fit_score >= 4 ? 'text-amber-400' : 'text-slate-500'}`}>
        {r.fit_score != null ? `${r.fit_score}/10` : '—'}
      </span>
    )},
  { id: 'tier', header: 'Tier',
    cell: ({ row: { original: r } }) => (
      <span className={`text-xs font-semibold ${TIER_COLOURS[r.tier ?? ''] ?? 'text-slate-500'}`}>{r.tier || '—'}</span>
    )},
  { id: 'confidence', header: 'Conf.',
    cell: ({ row: { original: r } }) => <span className="text-slate-500 text-xs">{r.confidence || '—'}</span> },
  { id: 'disqualified', header: 'DQ',
    cell: ({ row: { original: r } }) => r.disqualified
      ? <span className="text-red-400 text-xs">✗</span>
      : <span className="text-slate-700 text-xs">—</span> },
  { id: 'score_reason', header: 'Reason',
    cell: ({ row: { original: r } }) => (
      <span className="text-slate-500 text-xs max-w-xs truncate block" title={r.score_reason ?? ''}>{r.score_reason || '—'}</span>
    )},
]

function ScoredLeadsTable({ refresh }: { refresh: number }) {
  const [data, setData] = useState<ScoredLeadsResponse | null>(null)
  const [page, setPage] = useState(1)
  const [tier, setTier] = useState('')

  const fetchData = useCallback(() => {
    const params = new URLSearchParams({ page: String(page), per_page: '100' })
    if (tier) params.set('tier', tier)
    fetch(`${API}/scoring/leads?${params}`)
      .then(r => r.json()).then((d: ScoredLeadsResponse) => setData(d)).catch(() => {})
  }, [page, tier, refresh]) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => { fetchData() }, [fetchData])

  const table = useReactTable({
    data: data?.results ?? [],
    columns: RESULTS_COLS,
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data?.pages ?? 1,
  })

  if (!data || data.total === 0) {
    return <p className="text-slate-600 text-sm text-center py-10">No scored leads yet — run scoring above.</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        <span className="text-slate-300 text-sm font-semibold flex-1">Scored Leads</span>
        <span className="text-slate-500 text-xs">{data.total.toLocaleString()} scored</span>
        <select value={tier} onChange={e => { setTier(e.target.value); setPage(1) }}
          className="px-2 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500">
          <option value="">All tiers</option>
          {['A','B','C','D','skip'].map(t => <option key={t} value={t}>Tier {t}</option>)}
        </select>
      </div>
      <div className="rounded-xl border border-slate-700 bg-slate-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id} className="border-b border-slate-700">
                {hg.headers.map(h => (
                  <th key={h.id} className="px-3 py-3 text-left text-xs font-semibold text-indigo-300 uppercase tracking-wider whitespace-nowrap">
                    {flexRender(h.column.columnDef.header, h.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map(row => (
              <tr key={row.id} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.pages > 1 && (
        <div className="flex items-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700 transition-colors">Previous</button>
          <span className="text-slate-400 text-sm">{page} / {data.pages}</span>
          <button onClick={() => setPage(p => Math.min(data.pages, p + 1))} disabled={page === data.pages}
            className="px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700 transition-colors">Next</button>
        </div>
      )}
    </div>
  )
}

// ─── Tab root ─────────────────────────────────────────────────────────────────

export function ScoringTab() {
  const [specs, setSpecs]           = useState<string[]>([])
  const [resultsKey, setResultsKey] = useState(0)

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-6">
        <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
          <SpecEditor onSpecsChange={setSpecs} />
        </div>
        <div className="rounded-xl border border-slate-700 bg-slate-800 p-5">
          <RunPanel specs={specs} onDone={() => setResultsKey(k => k + 1)} />
        </div>
      </div>
      <ScoredLeadsTable refresh={resultsKey} />
    </div>
  )
}

const TEMPLATE = `# icp_spec.yaml
# Pass to score_leads.py with --spec specs/icp_spec.yaml

offer: >
  Describe your offer here.

primary_signals:
  - Signal 1
  - Signal 2

secondary_signals:
  - Supporting signal

hard_disqualifiers:
  - Absolute deal-breaker

value_blockers:
  - Soft penalty

anchors:
  "10": Perfect match description
  "7-9": Strong match description
  "4-6": Partial match description
  "1-3": Poor match description
`
