import ResultsTable from '@/components/ResultsTable'

export default function TestResultsPage() {
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Test Results</h2>
        <p className="text-xs text-text-muted mt-1">
          View historical test execution runs and drill into individual results.
        </p>
      </div>

      <section className="rounded-lg border border-border-default bg-bg-secondary shadow-card p-6">
        <ResultsTable />
      </section>
    </div>
  )
}
