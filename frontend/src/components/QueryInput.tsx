import { useState } from 'react'
import { useAppStore } from '@/store/appStore'
import { executeQuery } from '@/api/queryApi'
import type { QueryMode } from '@/types'

export default function QueryInput() {
  const [mode, setMode] = useState<QueryMode>('nlp')
  const [input, setInput] = useState('')
  const isQuerying = useAppStore((s) => s.isQuerying)
  const setIsQuerying = useAppStore((s) => s.setIsQuerying)
  const setLastQueryResult = useAppStore((s) => s.setLastQueryResult)
  const addLog = useAppStore((s) => s.addLog)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!input.trim() || isQuerying) return

    setIsQuerying(true)
    addLog('info', `Executing ${mode.toUpperCase()} query...`)

    try {
      const result = await executeQuery(input, mode)
      setLastQueryResult(result)
      addLog('success', `Query returned ${result.row_count} rows in ${result.execution_time_ms}ms`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog('error', `Query failed: ${msg}`)
      setLastQueryResult(null)
    } finally {
      setIsQuerying(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* Mode toggle */}
      <div className="flex items-center gap-2">
        <span className="text-xs font-medium text-text-secondary">Mode:</span>
        <div className="flex rounded-lg border border-border-default overflow-hidden">
          <button
            type="button"
            onClick={() => setMode('nlp')}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === 'nlp'
                ? 'bg-accent-primary text-white'
                : 'bg-bg-secondary text-text-secondary hover:bg-bg-input'
            }`}
          >
            💬 Natural Language
          </button>
          <button
            type="button"
            onClick={() => setMode('sql')}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              mode === 'sql'
                ? 'bg-accent-primary text-white'
                : 'bg-bg-secondary text-text-secondary hover:bg-bg-input'
            }`}
          >
            🗃️ SQL
          </button>
        </div>
      </div>

      {/* Input */}
      <textarea
        value={input}
        onChange={(e) => setInput(e.target.value)}
        placeholder={
          mode === 'nlp'
            ? 'Ask a question about your data... e.g. "Show all records where amount > 1000 after ETL"'
            : 'SELECT * FROM target_table WHERE ...'
        }
        rows={4}
        className="w-full rounded-lg border border-border-default bg-bg-input px-4 py-3 text-sm
          font-mono focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20
          placeholder:text-text-muted resize-none"
      />

      {/* Submit */}
      <button
        type="submit"
        disabled={!input.trim() || isQuerying}
        className="px-4 py-2 rounded-md bg-accent-primary text-white text-sm font-medium
          hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isQuerying ? '⏳ Running...' : '▶️ Run Query'}
      </button>
    </form>
  )
}
