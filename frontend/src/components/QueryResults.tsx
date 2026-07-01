import { useAppStore } from '@/store/appStore'

export default function QueryResults() {
  const result = useAppStore((s) => s.lastQueryResult)

  if (!result) return null

  return (
    <div className="space-y-4 animate-slide-up">
      {/* Generated SQL */}
      {result.generated_sql && (
        <div className="space-y-1">
          <h4 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
            Generated SQL
          </h4>
          <div className="rounded-lg bg-[#0f172a] p-4">
            <code className="text-xs text-green-400 font-mono whitespace-pre-wrap">
              {result.generated_sql}
            </code>
          </div>
        </div>
      )}

      {/* Results meta */}
      <div className="flex items-center gap-4 text-xs text-text-muted">
        <span>{result.row_count} rows returned</span>
        <span>•</span>
        <span>{result.execution_time_ms}ms</span>
      </div>

      {/* Data table */}
      {result.columns.length > 0 && result.rows.length > 0 && (
        <div className="rounded-lg border border-border-default overflow-hidden">
          <div className="overflow-x-auto max-h-72">
            <table className="w-full text-xs">
              <thead className="bg-bg-input sticky top-0">
                <tr>
                  {result.columns.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-left font-semibold text-text-secondary border-b border-border-default"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((row, i) => (
                  <tr
                    key={i}
                    className="border-b border-border-subtle hover:bg-bg-input/50 transition-colors"
                  >
                    {result.columns.map((col) => (
                      <td key={col} className="px-3 py-2 text-text-primary font-mono">
                        {row[col] == null ? (
                          <span className="text-text-muted italic">NULL</span>
                        ) : (
                          String(row[col])
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
