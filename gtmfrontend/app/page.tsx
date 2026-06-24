'use client'

import { useState } from 'react'
import { Sidebar, type Tab } from './components/Sidebar'
import { Overview } from './components/Overview'
import { LeadsTable } from './components/LeadsTable'

export default function HomePage() {
  const [tab, setTab] = useState<Tab>('overview')

  return (
    <div className="flex min-h-screen" style={{ background: '#0f172a' }}>
      <Sidebar tab={tab} setTab={setTab} />
      <main className="flex-1 ml-52 min-w-0 overflow-hidden px-8 py-8">
        {tab === 'overview' && <Overview />}
        {tab === 'leads'    && <LeadsTable />}
      </main>
    </div>
  )
}
