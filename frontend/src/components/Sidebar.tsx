import { useAppStore } from '@/store/appStore'
import type { ActiveTab } from '@/types'
import { useState } from 'react'

const navItems: { id: ActiveTab; label: string; icon: string }[] = [
  { id: 'run-tests', label: 'Run Tests', icon: '🚀' },
  { id: 'query-validator', label: 'Query Validator', icon: '🔍' },
  { id: 'results', label: 'Test Results', icon: '📊' },
]

export default function Sidebar() {
  const activeTab = useAppStore((s) => s.activeTab)
  const setActiveTab = useAppStore((s) => s.setActiveTab)
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside
      className={`
        flex flex-col h-full bg-bg-sidebar border-r border-border-default
        transition-all duration-200 ease-in-out shrink-0
        ${collapsed ? 'w-[48px]' : 'w-[260px]'}
      `}
    >
      {/* Header */}
      <div className={`flex items-center gap-3 p-4 border-b border-white/10 ${collapsed ? 'justify-center' : ''}`}>
        <span className="text-xl shrink-0">🧪</span>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-text-inverse truncate">AetherTest</h1>
            <p className="text-xs text-text-muted truncate">Data Flow Testing</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-2 space-y-1" aria-label="Main navigation">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveTab(item.id)}
            className={`
              w-full flex items-center gap-3 rounded-lg text-sm font-medium transition-colors
              ${collapsed ? 'justify-center px-2 py-3' : 'px-3 py-2.5'}
              ${activeTab === item.id
                ? 'bg-accent-primary/20 text-accent-primary'
                : 'text-text-inverse/70 hover:bg-white/5 hover:text-text-inverse'
              }
            `}
            title={collapsed ? item.label : undefined}
            aria-current={activeTab === item.id ? 'page' : undefined}
          >
            <span className="text-lg shrink-0">{item.icon}</span>
            {!collapsed && <span className="truncate">{item.label}</span>}
          </button>
        ))}
      </nav>

      {/* Collapse toggle */}
      <div className="p-2 border-t border-white/10">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg
            text-xs text-text-inverse/60 hover:text-text-inverse hover:bg-white/5 transition-colors"
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          <span className="text-sm">{collapsed ? '▶' : '◀'}</span>
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  )
}
