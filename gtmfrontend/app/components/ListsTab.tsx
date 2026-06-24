'use client'

import { useEffect, useState, useCallback } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'

interface LeadList {
  id: number
  name: string
  created_at: string
  entry_count: number
}

interface ListEntry {
  id: number
  full_name: string | null
  title: string | null
  email: string | null
  company_name: string | null
  lead_country: string | null
  seniority: string | null
}

interface ListDetail extends LeadList {
  entries: ListEntry[]
}

export function ListsTab() {
  const [lists, setLists]         = useState<LeadList[]>([])
  const [loading, setLoading]     = useState(true)
  const [expandedId, setExpandedId] = useState<number | null>(null)
  const [detail, setDetail]       = useState<ListDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  const fetchLists = useCallback(() => {
    fetch(`${API}/lists`)
      .then(r => r.json())
      .then((rows: LeadList[]) => { setLists(rows); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  useEffect(() => { fetchLists() }, [fetchLists])

  const expand = (lst: LeadList) => {
    if (expandedId === lst.id) {
      setExpandedId(null)
      setDetail(null)
      return
    }
    setExpandedId(lst.id)
    setDetailLoading(true)
    fetch(`${API}/lists/${lst.id}`)
      .then(r => r.json())
      .then((d: ListDetail) => { setDetail(d); setDetailLoading(false) })
      .catch(() => setDetailLoading(false))
  }

  const removeEntry = (listId: number, leadId: number) => {
    fetch(`${API}/lists/${listId}/entries/${leadId}`, { method: 'DELETE' })
      .then(() => {
        setDetail(prev => prev
          ? { ...prev, entries: prev.entries.filter(e => e.id !== leadId), entry_count: prev.entry_count - 1 }
          : prev)
        setLists(prev => prev.map(l => l.id === listId ? { ...l, entry_count: l.entry_count - 1 } : l))
      })
      .catch(() => {})
  }

  const deleteList = (listId: number) => {
    fetch(`${API}/lists/${listId}`, { method: 'DELETE' })
      .then(() => {
        setLists(prev => prev.filter(l => l.id !== listId))
        if (expandedId === listId) { setExpandedId(null); setDetail(null) }
      })
      .catch(() => {})
  }

  const downloadCsv = (lst: LeadList) => {
    window.open(`${API}/lists/${lst.id}/export`, '_blank')
  }

  if (loading) {
    return <div className="flex items-center justify-center h-48 text-slate-500 text-sm">Loading…</div>
  }

  if (lists.length === 0) {
    return (
      <div className="mt-20 text-center text-slate-500 text-sm">
        No lists yet — select leads in the Leads tab and save them to a list.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="text-slate-400 text-sm">
        {lists.length} {lists.length === 1 ? 'list' : 'lists'}
      </div>

      {lists.map(lst => (
        <div key={lst.id} className="rounded-xl border border-slate-700 bg-slate-800 overflow-hidden">
          <div
            className="flex items-center gap-3 px-5 py-3.5 cursor-pointer hover:bg-slate-700/30 transition-colors"
            onClick={() => expand(lst)}>
            <span className="text-slate-400 text-sm">{expandedId === lst.id ? '▾' : '▸'}</span>
            <span className="text-white font-semibold flex-1">{lst.name}</span>
            <span className="text-slate-500 text-xs mr-2">
              {lst.entry_count} {lst.entry_count === 1 ? 'lead' : 'leads'}
            </span>
            <span className="text-slate-600 text-xs mr-3">{lst.created_at.slice(0, 10)}</span>
            <button
              onClick={e => { e.stopPropagation(); downloadCsv(lst) }}
              className="px-2 py-1 rounded text-xs text-slate-400/60 hover:text-slate-300 hover:bg-slate-700/40 transition-colors">
              ↓ CSV
            </button>
            <button
              onClick={e => { e.stopPropagation(); deleteList(lst.id) }}
              className="px-2 py-1 rounded text-xs text-red-400/60 hover:text-red-300 hover:bg-red-900/20 transition-colors">
              Delete
            </button>
          </div>

          {expandedId === lst.id && (
            <div className="border-t border-slate-700">
              {detailLoading && (
                <div className="px-5 py-6 text-center text-slate-500 text-sm">Loading…</div>
              )}
              {!detailLoading && detail && detail.entries.length === 0 && (
                <div className="px-5 py-6 text-center text-slate-500 text-sm">This list has no entries.</div>
              )}
              {!detailLoading && detail && detail.entries.length > 0 && (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700 bg-slate-800/50">
                      {['Name', 'Title', 'Email', 'Company', 'Country', 'Seniority', ''].map(h => (
                        <th key={h} className={`px-4 py-2 text-left text-xs font-semibold text-indigo-300 uppercase tracking-wider ${h === '' ? 'w-8' : ''}`}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {detail.entries.map(entry => (
                      <tr key={entry.id} className="border-b border-slate-700/50 hover:bg-slate-700/20">
                        <td className="px-4 py-2 text-slate-200 text-xs whitespace-nowrap">{entry.full_name || '—'}</td>
                        <td className="px-4 py-2 text-slate-400 text-xs">{entry.title || '—'}</td>
                        <td className="px-4 py-2 text-xs">
                          {entry.email
                            ? <a href={`mailto:${entry.email}`} className="text-emerald-400 hover:text-emerald-300">{entry.email}</a>
                            : <span className="text-slate-700">—</span>}
                        </td>
                        <td className="px-4 py-2 text-slate-400 text-xs whitespace-nowrap">{entry.company_name || '—'}</td>
                        <td className="px-4 py-2 text-slate-400 text-xs whitespace-nowrap">{entry.lead_country || '—'}</td>
                        <td className="px-4 py-2 text-slate-500 text-xs">{entry.seniority?.replace(/_/g, ' ') || '—'}</td>
                        <td className="px-4 py-2">
                          <button
                            onClick={() => removeEntry(lst.id, entry.id)}
                            className="text-slate-600 hover:text-red-400 text-base leading-none transition-colors">
                            ×
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
