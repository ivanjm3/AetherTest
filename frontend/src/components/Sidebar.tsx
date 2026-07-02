import { useAppStore } from '@/store/appStore'
import { useSessionStore } from '@/store/sessionStore'
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

  const sessions = useSessionStore((s) => s.sessions)
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const createSession = useSessionStore((s) => s.createSession)
  const switchSession = useSessionStore((s) => s.switchSession)
  const deleteSession = useSessionStore((s) => s.deleteSession)
  const renameSession = useSessionStore((s) => s.renameSession)

  const [editingId, setEditingId] = useState<string | null>(null)
  const [editName, setEditName] = useState('')

  function handleStartRename(id: string, currentName: string) {
    setEditingId(id)
    setEditName(currentName)
  }

  function handleFinishRename(id: string) {
    if (editName.trim()) {
      renameSession(id, editName.trim())
    }
    setEditingId(null)
  }

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
        <span className="text-xl shrink-0"> </span>
        {!collapsed && (
          <div className="min-w-0">
            <h1 className="text-sm font-bold text-text-inverse truncate">AetherTest</h1>
            <p className="text-xs text-text-muted truncate">Data Flow Testing</p>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="p-2 space-y-1" aria-label="Main navigation">
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

      {/* Sessions section */}
      {!collapsed && (
        <div className="flex-1 flex flex-col min-h-0 border-t border-white/10">
          <div className="flex items-center justify-between px-3 py-2">
            <span className="text-xs font-semibold text-text-inverse/60 uppercase tracking-wider">Sessions</span>
            <button
              onClick={() => createSession()}
              className="text-xs px-2 py-1 rounded text-text-inverse/50 hover:text-accent-primary hover:bg-white/5 transition-colors"
              title="New session"
            >
              ＋ New
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
            {sessions.length === 0 && (
              <div className="px-2 py-6 text-center">
                <span className="text-2xl block mb-2">📋</span>
                <p className="text-xs text-text-inverse/40">No sessions yet</p>
                <p className="text-[10px] text-text-inverse/30 mt-1">
                  A session is created automatically when you analyze a pipeline
                </p>
              </div>
            )}

            {sessions.map((session) => (
              <div
                key={session.id}
                className={`
                  group flex items-center gap-2 px-2 py-2 rounded-lg cursor-pointer transition-colors
                  ${activeSessionId === session.id
                    ? 'bg-accent-primary/20 text-accent-primary'
                    : 'text-text-inverse/70 hover:bg-white/5 hover:text-text-inverse'
                  }
                `}
                onClick={() => switchSession(session.id)}
              >
                <span className="text-sm shrink-0">
                  {activeSessionId === session.id ? '▸' : '○'}
                </span>
                <div className="flex-1 min-w-0">
                  {editingId === session.id ? (
                    <input
                      type="text"
                      value={editName}
                      onChange={(e) => setEditName(e.target.value)}
                      onBlur={() => handleFinishRename(session.id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleFinishRename(session.id)
                        if (e.key === 'Escape') setEditingId(null)
                      }}
                      onClick={(e) => e.stopPropagation()}
                      autoFocus
                      className="w-full bg-transparent border-b border-accent-primary text-xs text-text-inverse outline-none px-0 py-0"
                    />
                  ) : (
                    <>
                      <p className="text-xs font-medium truncate">{session.name}</p>
                      <p className="text-[10px] text-text-muted truncate">
                        {new Date(session.updatedAt).toLocaleDateString()}
                        {session.state.testCases.length > 0 && (
                          <> · {session.state.testCases.length} tests</>
                        )}
                        {session.state.executionHistory.length > 0 && (
                          <> · {session.state.executionHistory.length} run{session.state.executionHistory.length > 1 ? 's' : ''}</>
                        )}
                      </p>
                    </>
                  )}
                </div>

                {/* Actions (visible on hover) */}
                {editingId !== session.id && (
                  <div className="hidden group-hover:flex items-center gap-0.5 shrink-0">
                    <button
                      onClick={(e) => { e.stopPropagation(); handleStartRename(session.id, session.name) }}
                      className="text-[10px] px-1 py-0.5 rounded hover:bg-white/10 text-text-inverse/50 hover:text-text-inverse"
                      title="Rename"
                    >
                      ✏️
                    </button>
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteSession(session.id) }}
                      className="text-[10px] px-1 py-0.5 rounded hover:bg-red-500/20 text-text-inverse/50 hover:text-red-400"
                      title="Delete"
                    >
                      🗑️
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Collapsed sessions indicator */}
      {collapsed && sessions.length > 0 && (
        <div className="flex-1 flex flex-col items-center pt-2 border-t border-white/10">
          <button
            onClick={() => setCollapsed(false)}
            className="w-8 h-8 flex items-center justify-center rounded-lg text-text-inverse/50 hover:text-text-inverse hover:bg-white/5 transition-colors"
            title={`${sessions.length} session(s)`}
          >
            <span className="text-xs">{sessions.length}</span>
          </button>
        </div>
      )}

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
