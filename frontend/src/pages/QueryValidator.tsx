import QueryInput from '@/components/QueryInput'
import QueryResults from '@/components/QueryResults'

export default function QueryValidator() {
  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h2 className="text-base font-semibold text-text-primary">Query Validator</h2>
        <p className="text-xs text-text-muted mt-1">
          Validate end-state data using natural language or SQL queries against your warehouse output.
        </p>
      </div>

      <section className="rounded-lg border border-border-default bg-bg-secondary shadow-card p-6 space-y-4">
        <QueryInput />
      </section>

      <section className="rounded-lg border border-border-default bg-bg-secondary shadow-card p-6">
        <QueryResults />
      </section>
    </div>
  )
}
