'use client'

import { useEffect, useRef, useState } from 'react'

const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8002'

interface ExistingList {
  id: number
  name: string
  entry_count: number
}

interface Props {
  leadIds: number[]
  onClose: () => void
  onSaved: () => void
}

export function SaveToListDialog({ leadIds, onClose, onSaved }: Props) {
  const [lists, setLists]       = useState<ExistingList[]>([])
  const [mode, setMode]         = useState<'new' | 'existing'>('new')
  const [newName, setNewName]   = useState('')
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [saving, setSaving]     = useState(false)
  const [error, setError]       = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    fetch(`${API}/lists`)
      .then(r => r.json())
      .then((rows: ExistingList[]) => {
        setLists(rows)
        if (rows.length === 0) setMode('new')
      })
      .catch(() => {})
    setTimeout(() => inputRef.current?.focus(), 50)
  }, [])

  const save = async () => {
    if (mode === 'new' && !newName.trim()) return
    if (mode === 'existing' && selectedId === null) return
    setSaving(true)
    setError('')
    try {
      let res: Response
      if (mode === 'new') {
        res = await fetch(`${API}/lists`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ name: newName.trim(), lead_ids: leadIds }),
        })
      } else {
        res = await fetch(`${API}/lists/${selectedId}/entries`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ lead_ids: leadIds }),
        })
      }
      if (!res.ok) {
        const msg = await res.text().catch(() => `HTTP ${res.status}`)
        setError(msg || `HTTP ${res.status}`)
        setSaving(false)
        return
      }
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Network error — is the backend running?')
      setSaving(false)
    }
  }

  const canSave = mode === 'new' ? newName.trim().length > 0 : selectedId !== null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className="w-96 rounded-2xl border border-slate-700 bg-slate-900 shadow-2xl p-6 space-y-5">
        <div className="flex items-center justify-between">
          <h2 className="text-white font-semibold">Save {leadIds.length} lead{leadIds.length !== 1 ? 's' : ''} to list</h2>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 text-xl leading-none">×</button>
        </div>

        {lists.length > 0 && (
          <div className="flex gap-3">
            {(['new', 'existing'] as const).map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`flex-1 py-2 rounded-lg text-sm font-medium transition-colors border ${
                  mode === m
                    ? 'bg-indigo-600/20 text-indigo-300 border-indigo-600/40'
                    : 'text-slate-400 border-slate-700 hover:text-slate-200 hover:bg-slate-800'
                }`}>
                {m === 'new' ? 'New list' : 'Existing list'}
              </button>
            ))}
          </div>
        )}

        {mode === 'new' && (
          <input
            ref={inputRef}
            type="text"
            placeholder="List name…"
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && canSave) save() }}
            className="w-full px-3 py-2.5 rounded-lg border border-slate-600 bg-slate-800 text-slate-200 text-sm placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
        )}

        {mode === 'existing' && (
          <div className="space-y-1.5 max-h-48 overflow-y-auto">
            {lists.map(l => (
              <label key={l.id}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border cursor-pointer transition-colors ${
                  selectedId === l.id
                    ? 'border-indigo-600/40 bg-indigo-600/10'
                    : 'border-slate-700 hover:bg-slate-800'
                }`}>
                <input type="radio" name="list" value={l.id}
                  checked={selectedId === l.id}
                  onChange={() => setSelectedId(l.id)}
                  className="accent-indigo-500" />
                <span className="text-slate-200 text-sm flex-1">{l.name}</span>
                <span className="text-slate-500 text-xs">{l.entry_count}</span>
              </label>
            ))}
          </div>
        )}

        {error && (
          <div className="text-red-400 text-xs bg-red-900/20 border border-red-800/40 rounded-lg px-3 py-2">
            {error}
          </div>
        )}

        <div className="flex gap-3 pt-1">
          <button onClick={onClose}
            className="flex-1 py-2 rounded-lg border border-slate-600 text-slate-300 text-sm hover:bg-slate-800 transition-colors">
            Cancel
          </button>
          <button onClick={save} disabled={!canSave || saving}
            className="flex-1 py-2 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-500 disabled:opacity-40 transition-colors">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
