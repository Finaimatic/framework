'use client'

export type Tab = 'overview' | 'leads'

const NAV: { tab: Tab; label: string }[] = [
  { tab: 'overview', label: 'Overview' },
  { tab: 'leads',    label: 'Leads' },
]

interface SidebarProps {
  tab: Tab
  setTab: (tab: Tab) => void
}

export function Sidebar({ tab, setTab }: SidebarProps) {
  return (
    <aside
      className="fixed top-0 left-0 h-full w-52 flex flex-col border-r border-slate-700/80 z-50"
      style={{ background: '#0b1120' }}
    >
      <div className="px-5 py-5 border-b border-slate-700/60">
        <span className="text-white font-bold text-sm tracking-tight">Finaimatic GTM</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ tab: t, label }) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`w-full flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              tab === t
                ? 'bg-indigo-600/20 text-indigo-300 border border-indigo-600/40'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            {label}
          </button>
        ))}
      </nav>
    </aside>
  )
}
