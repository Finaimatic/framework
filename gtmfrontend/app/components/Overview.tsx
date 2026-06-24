'use client'

import { useEffect, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'

interface OverviewData {
  total: number
  with_email: number
  with_linkedin: number
  by_country: { label: string; count: number }[]
  by_seniority: { label: string; count: number }[]
  by_import: { label: string; count: number }[]
  by_industry: { label: string; count: number }[]
}

function StatCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800 px-6 py-5">
      <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">{label}</div>
      <div className="text-2xl font-semibold text-slate-100">{typeof value === 'number' ? value.toLocaleString() : value}</div>
      {sub && <div className="text-slate-500 text-xs mt-0.5">{sub}</div>}
    </div>
  )
}

function BarList({ rows, total }: { rows: { label: string; count: number }[]; total: number }) {
  if (!rows.length) return <div className="text-slate-600 text-sm">No data</div>
  const max = rows[0].count
  return (
    <div className="space-y-2">
      {rows.map(r => (
        <div key={r.label} className="flex items-center gap-3">
          <div className="w-28 shrink-0 text-slate-400 text-xs truncate" title={r.label}>{r.label}</div>
          <div className="flex-1 bg-slate-700 rounded-full h-1.5 overflow-hidden">
            <div
              className="h-full bg-indigo-500 rounded-full"
              style={{ width: `${(r.count / max) * 100}%` }}
            />
          </div>
          <div className="w-16 text-right text-slate-400 text-xs shrink-0">
            {r.count.toLocaleString()}
            <span className="text-slate-600 ml-1">({Math.round((r.count / total) * 100)}%)</span>
          </div>
        </div>
      ))}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-700 bg-slate-800 px-6 py-5">
      <div className="text-slate-300 text-sm font-semibold mb-4">{title}</div>
      {children}
    </div>
  )
}

export function Overview() {
  const [data, setData]       = useState<OverviewData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`${API}/overview`)
      .then(r => r.json())
      .then((d: OverviewData) => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48 text-slate-500 text-sm">Loading…</div>
    )
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-48 text-red-400 text-sm">Failed to load overview.</div>
    )
  }

  const pct = (n: number) => data.total ? `${Math.round((n / data.total) * 100)}%` : '—'

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total leads" value={data.total} />
        <StatCard label="With email" value={data.with_email} sub={pct(data.with_email)} />
        <StatCard label="With LinkedIn" value={data.with_linkedin} sub={pct(data.with_linkedin)} />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Section title="Top countries">
          <BarList rows={data.by_country} total={data.total} />
        </Section>
        <Section title="By seniority">
          <BarList rows={data.by_seniority} total={data.total} />
        </Section>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <Section title="By import">
          <BarList rows={data.by_import} total={data.total} />
        </Section>
        <Section title="Top industries">
          <BarList rows={data.by_industry} total={data.total} />
        </Section>
      </div>
    </div>
  )
}
