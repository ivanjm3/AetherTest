import type { ExecutionRun } from '@/types'

/**
 * Trigger a browser download with given content.
 */
function downloadFile(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Export a single execution run as CSV.
 */
export function exportRunAsCSV(run: ExecutionRun) {
  const headers = ['test_id', 'test_name', 'description', 'status', 'actual', 'expected', 'duration_ms', 'error_message']
  const rows = run.results.map((r) =>
    headers.map((h) => {
      const val = String((r as unknown as Record<string, unknown>)[h] ?? '')
      // Escape CSV: wrap in quotes if contains comma/newline/quote
      if (val.includes(',') || val.includes('\n') || val.includes('"')) {
        return `"${val.replace(/"/g, '""')}"`
      }
      return val
    }).join(',')
  )

  const csv = [headers.join(','), ...rows].join('\n')
  const timestamp = new Date(run.timestamp).toISOString().slice(0, 19).replace(/:/g, '-')
  downloadFile(csv, `test-results-${run.id.slice(0, 8)}-${timestamp}.csv`, 'text/csv')
}

/**
 * Export a single execution run as JSON (includes analysis if present).
 */
export function exportRunAsJSON(run: ExecutionRun) {
  const json = JSON.stringify(run, null, 2)
  const timestamp = new Date(run.timestamp).toISOString().slice(0, 19).replace(/:/g, '-')
  downloadFile(json, `test-results-${run.id.slice(0, 8)}-${timestamp}.json`, 'application/json')
}

/**
 * Export all execution runs as a single JSON file.
 */
export function exportAllRunsAsJSON(runs: ExecutionRun[]) {
  const json = JSON.stringify(runs, null, 2)
  const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-')
  downloadFile(json, `all-test-results-${timestamp}.json`, 'application/json')
}
