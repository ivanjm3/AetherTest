import { useRef, useEffect } from 'react'
import { useAppStore } from '@/store/appStore'

const levelStyles = {
  info: 'text-blue-400',
  success: 'text-green-400',
  error: 'text-red-400',
  warning: 'text-yellow-400',
}

const levelIcons = {
  info: 'ℹ️',
  success: '✅',
  error: '❌',
  warning: '⚠️',
}

export default function LogPanel() {
  const logs = useAppStore((s) => s.logs)
  const logPanelOpen = useAppStore((s) => s.logPanelOpen)
  const toggleLogPanel = useAppStore((s) => s.toggleLogPanel)
  const clearLogs = useAppStore((s) => s.clearLogs)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current && logPanelOpen) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [logs, logPanelOpen])

  return (
    <section className="border-t border-border-default bg-[#0f172a] transition-all duration-200">
      {/* Header / Toggle */}
      <button
        onClick={toggleLogPanel}
        className="w-full flex items-center justify-between px-4 py-2 text-sm text-text-inverse hover:bg-white/5 transition-colors"
        aria-expanded={logPanelOpen}
        aria-controls="log-panel-content"
      >
        <span className="flex items-center gap-2 font-medium">
          <span className="text-xs">📋</span>
          Output Log
          {logs.length > 0 && (
            <span className="bg-accent-primary/20 text-accent-primary text-xs px-1.5 py-0.5 rounded-full">
              {logs.length}
            </span>
          )}
        </span>
        <span className="text-text-muted text-xs">
          {logPanelOpen ? '▼ Collapse' : '▲ Expand'}
        </span>
      </button>

      {/* Content */}
      {logPanelOpen && (
        <div id="log-panel-content" className="animate-fade-in">
          <div className="flex justify-end px-4 pb-1">
            <button
              onClick={clearLogs}
              className="text-xs text-text-muted hover:text-text-inverse transition-colors"
            >
              Clear
            </button>
          </div>
          <div
            ref={scrollRef}
            className="px-4 pb-3 max-h-48 overflow-y-auto font-mono text-xs space-y-0.5"
          >
            {logs.length === 0 ? (
              <p className="text-text-muted italic">No logs yet. Run an action to see output here.</p>
            ) : (
              logs.map((log) => (
                <div key={log.id} className={`flex items-start gap-2 ${levelStyles[log.level]}`}>
                  <span className="shrink-0">{levelIcons[log.level]}</span>
                  <span className="text-text-muted shrink-0">
                    {new Date(log.timestamp).toLocaleTimeString()}
                  </span>
                  <span>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </section>
  )
}
