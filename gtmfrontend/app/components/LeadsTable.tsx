'use client'

import { useEffect, useState, useCallback } from 'react'
import {
  useReactTable,
  getCoreRowModel,
  flexRender,
  type ColumnDef,
  type RowSelectionState,
} from '@tanstack/react-table'
import { SaveToListDialog } from './SaveToListDialog'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'

const sel = 'px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-200 text-sm focus:outline-none focus:border-indigo-500'

export interface Lead {
  id: number
  full_name: string | null
  title: string | null
  seniority: string | null
  email: string | null
  company_name: string | null
  lead_country: string | null
  import_name: string
  created_at: string | null
  linkedin_link: string | null
  scraped: boolean
  fit_score: number | null
  tier: string | null
}

interface LeadsResponse {
  total: number
  page: number
  per_page: number
  pages: number
  results: Lead[]
}

function dim(v: React.ReactNode) {
  return <span className="text-slate-500 text-xs">{v ?? <span className="text-slate-700">—</span>}</span>
}
function bright(v: React.ReactNode) {
  return <span className="text-slate-200 text-xs">{v ?? <span className="text-slate-700">—</span>}</span>
}

const DATA_COLUMNS: ColumnDef<Lead, unknown>[] = [
  {
    id: 'full_name', header: 'Name',
    cell: ({ row: { original: r } }) => r.linkedin_link
      ? <a href={r.linkedin_link} target="_blank" rel="noopener noreferrer"
          className="text-indigo-400 hover:text-indigo-300 text-xs"
          onClick={e => e.stopPropagation()}>{r.full_name ?? '—'}</a>
      : bright(r.full_name),
  },
  {
    id: 'title', header: 'Title',
    cell: ({ row: { original: r } }) => (
      <span className="text-slate-300 text-xs">{r.title ?? <span className="text-slate-700">—</span>}</span>
    ),
  },
  {
    id: 'seniority', header: 'Seniority',
    cell: ({ row: { original: r } }) => dim(r.seniority?.replace(/_/g, ' ')),
  },
  {
    id: 'email', header: 'Email',
    cell: ({ row: { original: r } }) => r.email
      ? <a href={`mailto:${r.email}`} className="text-emerald-400 hover:text-emerald-300 text-xs"
          onClick={e => e.stopPropagation()}>{r.email}</a>
      : <span className="text-slate-700 text-xs">—</span>,
  },
  {
    id: 'company_name', header: 'Company',
    cell: ({ row: { original: r } }) => bright(r.company_name),
  },
  {
    id: 'scraped', header: 'Scraped',
    cell: ({ row: { original: r } }) => r.scraped
      ? <span className="text-emerald-400 text-xs">✓</span>
      : <span className="text-slate-700 text-xs">—</span>,
  },
  {
    id: 'fit_score', header: 'Score',
    cell: ({ row: { original: r } }) => r.fit_score != null
      ? <span className={`text-xs font-semibold ${r.fit_score >= 7 ? 'text-emerald-400' : r.fit_score >= 4 ? 'text-amber-400' : 'text-slate-500'}`}>
          {r.fit_score}/10{r.tier ? ` · ${r.tier}` : ''}
        </span>
      : <span className="text-slate-700 text-xs">—</span>,
  },
  {
    id: 'lead_country', header: 'Country',
    cell: ({ row: { original: r } }) => dim(r.lead_country),
  },
  {
    id: 'import_name', header: 'Import',
    cell: ({ row: { original: r } }) => dim(r.import_name),
  },
  {
    id: 'created_at', header: 'Added',
    cell: ({ row: { original: r } }) => dim(r.created_at ? r.created_at.slice(0, 10) : null),
  },
]

export function LeadsTable() {
  const [data, setData]               = useState<LeadsResponse | null>(null)
  const [loading, setLoading]         = useState(false)
  const [page, setPage]               = useState(1)
  const [search, setSearch]           = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [country, setCountry]         = useState('')
  const [countries, setCountries]     = useState<string[]>([])
  const [scraped, setScraped]         = useState('')
  const [scored, setScored]           = useState('')
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})
  const [saveDialogOpen, setSaveDialogOpen] = useState(false)

  useEffect(() => {
    fetch(`${API}/leads/countries`)
      .then(r => r.json())
      .then((rows: { lead_country: string }[]) => setCountries(rows.map(r => r.lead_country)))
      .catch(() => {})
  }, [])

  const fetchData = useCallback(() => {
    setLoading(true)
    const params = new URLSearchParams({ page: String(page), per_page: '50' })
    if (search)  params.set('search', search)
    if (country) params.set('country', country)
    if (scraped) params.set('scraped', scraped)
    if (scored)  params.set('scored', scored)
    fetch(`${API}/leads?${params}`)
      .then(r => r.json())
      .then((d: LeadsResponse) => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [page, search, country, scraped, scored])

  useEffect(() => { fetchData() }, [fetchData])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setSearch(searchInput)
    setPage(1)
  }

  const reset = () => {
    setSearchInput('')
    setSearch('')
    setCountry('')
    setScraped('')
    setScored('')
    setPage(1)
  }

  const checkboxCol: ColumnDef<Lead, unknown> = {
    id: 'select',
    header: ({ table }) => (
      <input type="checkbox"
        checked={table.getIsAllPageRowsSelected()}
        ref={el => { if (el) el.indeterminate = table.getIsSomePageRowsSelected() }}
        onChange={table.getToggleAllPageRowsSelectedHandler()}
        className="accent-indigo-500 cursor-pointer"
      />
    ),
    cell: ({ row }) => (
      <input type="checkbox"
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
        onClick={e => e.stopPropagation()}
        className="accent-indigo-500 cursor-pointer"
      />
    ),
  }

  const table = useReactTable({
    data: data?.results ?? [],
    columns: [checkboxCol, ...DATA_COLUMNS],
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    getRowId: row => String(row.id),
    getCoreRowModel: getCoreRowModel(),
    manualPagination: true,
    pageCount: data?.pages ?? 1,
    enableRowSelection: true,
  })

  const selectedIds = Object.keys(rowSelection).map(Number)
  const hasFilters = search || searchInput || country || scraped || scored

  return (
    <div className="space-y-4">
      <form onSubmit={handleSearch} className="flex flex-wrap gap-3 items-center">
        <input
          type="text"
          placeholder="Search name, email, company, title…"
          value={searchInput}
          onChange={e => setSearchInput(e.target.value)}
          className="px-3 py-2 rounded-lg border border-slate-600 bg-slate-800 text-slate-200 text-sm placeholder-slate-500 w-72 focus:outline-none focus:border-indigo-500"
        />
        <select value={country} onChange={e => { setCountry(e.target.value); setPage(1) }} className={sel}>
          <option value="">All countries</option>
          {countries.map(c => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={scraped} onChange={e => { setScraped(e.target.value); setPage(1) }} className={sel}>
          <option value="">All (scraped)</option>
          <option value="yes">Scraped</option>
          <option value="no">Not scraped</option>
        </select>
        <select value={scored} onChange={e => { setScored(e.target.value); setPage(1) }} className={sel}>
          <option value="">All (scored)</option>
          <option value="yes">Scored</option>
          <option value="no">Not scored</option>
        </select>
        <button type="submit"
          className="px-3 py-2 rounded-lg border border-indigo-600 bg-indigo-900/40 text-indigo-300 text-sm hover:bg-indigo-900/70 transition-colors">
          Search
        </button>
        {hasFilters && (
          <button type="button" onClick={reset}
            className="px-3 py-2 rounded-lg border border-slate-600 bg-slate-700 text-slate-300 text-sm hover:bg-slate-600 transition-colors">
            Reset
          </button>
        )}
        {selectedIds.length > 0 && (
          <button type="button" onClick={() => setSaveDialogOpen(true)}
            className="ml-auto px-3 py-2 rounded-lg border border-amber-600/60 bg-amber-900/30 text-amber-300 text-sm hover:bg-amber-900/50 transition-colors">
            Save {selectedIds.length} to list
          </button>
        )}
      </form>

      {data && (
        <div className="text-slate-400 text-sm">
          {data.total.toLocaleString()} leads · page {data.page} of {data.pages}
          {selectedIds.length > 0 && (
            <span className="ml-3 text-amber-400">{selectedIds.length} selected</span>
          )}
        </div>
      )}

      <div className="rounded-xl border border-slate-700 bg-slate-800 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            {table.getHeaderGroups().map(hg => (
              <tr key={hg.id} className="border-b border-slate-700">
                {hg.headers.map(header => (
                  <th key={header.id}
                    className="px-3 py-3 text-left text-xs font-semibold text-indigo-300 uppercase tracking-wider whitespace-nowrap">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {loading && (
              <tr><td colSpan={DATA_COLUMNS.length + 1} className="px-4 py-16 text-center">
                <div className="flex flex-col items-center gap-3 text-slate-400">
                  <svg className="animate-spin h-8 w-8 text-indigo-400" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                  </svg>
                  <span className="text-sm">Loading leads…</span>
                </div>
              </td></tr>
            )}
            {!loading && table.getRowModel().rows.map(row => (
              <tr key={row.id}
                className={`border-b border-slate-700/50 hover:bg-slate-700/30 cursor-pointer ${row.getIsSelected() ? 'bg-indigo-900/20' : ''}`}
                onClick={() => row.toggleSelected()}>
                {row.getVisibleCells().map(cell => (
                  <td key={cell.id} className="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {!loading && data?.results.length === 0 && (
              <tr><td colSpan={DATA_COLUMNS.length + 1} className="px-4 py-10 text-center text-slate-500 text-sm">
                No leads found.
              </td></tr>
            )}
          </tbody>
        </table>
      </div>

      {data && data.pages > 1 && (
        <div className="flex items-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700 transition-colors">
            Previous
          </button>
          <span className="text-slate-400 text-sm">{page} / {data.pages}</span>
          <button onClick={() => setPage(p => Math.min(data.pages, p + 1))} disabled={page === data.pages}
            className="px-3 py-1.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-300 text-sm disabled:opacity-40 hover:bg-slate-700 transition-colors">
            Next
          </button>
        </div>
      )}

      {saveDialogOpen && (
        <SaveToListDialog
          leadIds={selectedIds}
          onClose={() => setSaveDialogOpen(false)}
          onSaved={() => { setSaveDialogOpen(false); setRowSelection({}) }}
        />
      )}
    </div>
  )
}
