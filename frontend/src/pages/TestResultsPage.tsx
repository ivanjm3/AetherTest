import { useAppStore } from '@/store/appStore'
import ResultsTable from '@/components/ResultsTable'
import { exportRunAsCSV, exportRunAsJSON, exportAllRunsAsJSON } from '@/utils/exportResults'

export default function TestResultsPage() {
  const executionHistory = useAppStore((s) => s.executionHistory)

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-text-primary">Test Results</h2>
          <p className="text-xs text-text-muted mt-1">
            View historical test execution runs and drill into individual results.
          </p>
        </div>
        {executionHistory.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={() => exportAllRunsAsJSON(executionHistory)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md
                border border-border-default bg-bg-secondary text-text-secondary
                hover:bg-bg-input hover:text-text-primary transition-colors"
            >
              📥 Export All (JSON)
            </button>
            {executionHistory.length === 1 && (
              <button
                onClick={() => exportRunAsCSV(executionHistory[0])}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md
                  border border-border-default bg-bg-secondary text-text-secondary
                  hover:bg-bg-input hover:text-text-primary transition-colors"
              >
                📥 Export (CSV)
              </button>
            )}
          </div>
        )}
      </div>

      <section className="rounded-lg border border-border-default bg-bg-secondary shadow-card p-6">
        <ResultsTable />
      </section>
    </div>
  )
}
