import { useAppStore } from '@/store/appStore'
import type { ExecutionRun } from '@/types'
import { useState } from 'react'

const statusIcons = {
  passed: '✅',
  failed: '❌',
  skipped: '⏭️',
  error: '💥',
}

const severityColors = {
  critical: 'text-red-600 bg-red-50',
  high: 'text-orange-600 bg-orange-50',
  medium: 'text-yellow-600 bg-yellow-50',
  low: 'text-blue-600 bg-blue-50',
}

const classificationLabels: Record<string, string> = {
  application_defect: '🐛 Application Defect',
  test_data_issue: '📊 Test Data Issue',
  environment_instability: '🌐 Environment Issue',
  regression: '⏪ Regression',
}

export default function ResultsTable() {
  const executionHistory = useAppStore((s) => s.executionHistory)
  const [expandedId, setExpandedId] = useState<string | null>(null)

  if (executionHistory.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <span className="text-4xl mb-3">📭</span>
        <p className="text-text-secondary font-medium">No test runs yet</p>
        <p className="text-text-muted text-xs mt-1">
          Run tests from the "Run Tests" tab to see results here.
        </p>
      </div>
    )
  }

  function toggleExpand(id: string) {
    setExpandedId(expandedId === id ? null : id)
  }

  function passRate(run: ExecutionRun): number {
    return run.total > 0 ? Math.round((run.passed / run.total) * 100) : 0
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary">
        Execution History ({executionHistory.length} runs)
      </h3>

      <div className="space-y-2">
        {executionHistory.map((run) => (
          <div
            key={run.id}
            className="rounded-lg border border-border-default bg-bg-secondary shadow-card overflow-hidden"
          >
            {/* Summary row */}
            <button
              onClick={() => toggleExpand(run.id)}
              className="w-full flex items-center gap-4 px-4 py-3 hover:bg-bg-input/50 transition-colors text-left"
              aria-expanded={expandedId === run.id}
            >
              <span className="text-lg">
                {run.failed === 0 ? '✅' : '❌'}
              </span>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-text-primary">
                  Run #{run.id.slice(0, 8)}
                </p>
                <p className="text-xs text-text-muted">
                  {new Date(run.timestamp).toLocaleString()}
                </p>
              </div>
              <div className="flex items-center gap-3 text-xs">
                <span className="text-status-success font-medium">{run.passed} passed</span>
                {run.failed > 0 && (
                  <span className="text-status-error font-medium">{run.failed} failed</span>
                )}
                {(run.errors ?? 0) > 0 && (
                  <span className="text-orange-500 font-medium">{run.errors} errors</span>
                )}
                {run.skipped > 0 && (
                  <span className="text-text-muted">{run.skipped} skipped</span>
                )}
              </div>
              {/* Progress bar */}
              <div className="w-20 h-2 rounded-full bg-bg-input overflow-hidden">
                <div
                  className="h-full bg-status-success rounded-full transition-all"
                  style={{ width: `${passRate(run)}%` }}
                />
              </div>
              <span className="text-xs text-text-muted">
                {expandedId === run.id ? '▼' : '▶'}
              </span>
            </button>

            {/* Detail view */}
            {expandedId === run.id && (
              <div className="border-t border-border-default animate-fade-in">
                {/* Test results */}
                <div className="px-4 py-3 space-y-1 bg-bg-input/30">
                  {run.results.map((r) => (
                    <div
                      key={r.test_id}
                      className="flex items-start gap-3 py-2.5 px-3 rounded-md hover:bg-bg-secondary transition-colors"
                    >
                      <span className="mt-0.5">{statusIcons[r.status]}</span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-text-primary">{r.test_name}</p>
                        {r.description && (
                          <p className="text-xs text-text-secondary mt-0.5">{r.description}</p>
                        )}
                        {r.status === 'failed' && r.actual && (
                          <p className="text-xs text-status-error mt-1 font-mono">
                            Actual: {r.actual}
                          </p>
                        )}
                        {r.status === 'error' && r.error_message && (
                          <p className="text-xs text-status-error mt-1" title={r.error_message}>
                            {r.error_message.slice(0, 120)}{r.error_message.length > 120 ? '...' : ''}
                          </p>
                        )}
                      </div>
                      <span className="text-xs text-text-muted font-mono shrink-0">{r.duration_ms}ms</span>
                    </div>
                  ))}
                </div>

                {/* Analysis section */}
                {run.analysis && (
                  <div className="border-t border-border-default px-4 py-4 space-y-4 bg-bg-secondary">
                    {/* Analysis summary */}
                    <div>
                      <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2">
                        🔍 Failure Analysis
                      </h4>
                      <div className="flex gap-4 mt-2">
                        <div className="px-3 py-2 rounded-lg bg-red-50 border border-red-200">
                          <p className="text-lg font-bold text-red-700">{run.analysis.summary.real_defects}</p>
                          <p className="text-xs text-red-600">Real Defects</p>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-yellow-50 border border-yellow-200">
                          <p className="text-lg font-bold text-yellow-700">{run.analysis.summary.false_positives}</p>
                          <p className="text-xs text-yellow-600">False Positives</p>
                        </div>
                        <div className="px-3 py-2 rounded-lg bg-blue-50 border border-blue-200">
                          <p className="text-lg font-bold text-blue-700">{run.analysis.summary.total_failures}</p>
                          <p className="text-xs text-blue-600">Total Analyzed</p>
                        </div>
                        {run.analysis.summary.regressions != null && run.analysis.summary.regressions > 0 && (
                          <div className="px-3 py-2 rounded-lg bg-purple-50 border border-purple-200">
                            <p className="text-lg font-bold text-purple-700">{run.analysis.summary.regressions}</p>
                            <p className="text-xs text-purple-600">Regressions</p>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Individual analyses */}
                    {run.analysis.analyses.length > 0 && (
                      <div className="space-y-2">
                        <h5 className="text-xs font-semibold text-text-secondary uppercase tracking-wide">
                          Root Cause Analysis
                        </h5>
                        {run.analysis.analyses.map((a) => (
                          <div
                            key={a.failure_id}
                            className="rounded-lg border border-border-default p-3 space-y-2"
                          >
                            <div className="flex items-start justify-between gap-2">
                              <p className="text-sm font-medium text-text-primary">{a.test_name}</p>
                              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${severityColors[a.severity] || 'text-gray-600 bg-gray-50'}`}>
                                {a.severity}
                              </span>
                            </div>
                            <div className="flex items-center gap-2 text-xs">
                              <span>{classificationLabels[a.classification] || a.classification}</span>
                              <span className="text-text-muted">•</span>
                              <span className="text-text-muted">
                                {Math.round(a.confidence * 100)}% confidence
                              </span>
                              {a.is_false_positive && (
                                <>
                                  <span className="text-text-muted">•</span>
                                  <span className="text-yellow-600 font-medium">False Positive</span>
                                </>
                              )}
                            </div>
                            <p className="text-xs text-text-secondary">
                              <span className="font-medium">Root cause:</span> {a.root_cause_hypothesis}
                            </p>
                            <p className="text-xs text-text-secondary">
                              <span className="font-medium">Action:</span> {a.recommended_action}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Immediate attention */}
                    {run.analysis.requires_immediate_attention.length > 0 && (
                      <div className="rounded-lg border-2 border-red-300 bg-red-50 p-3">
                        <h5 className="text-xs font-bold text-red-700 uppercase tracking-wide mb-2">
                          ⚠️ Requires Immediate Attention
                        </h5>
                        {run.analysis.requires_immediate_attention.map((a) => (
                          <div key={a.failure_id} className="text-xs text-red-800 py-1">
                            <span className="font-medium">{a.test_name}:</span> {a.fix_suggestion}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                {/* Coverage summary */}
                <div className="border-t border-border-default px-4 py-3 bg-bg-secondary">
                  <h4 className="text-sm font-semibold text-text-primary flex items-center gap-2 mb-2">
                    📊 Coverage Summary
                  </h4>
                  <div className="grid grid-cols-4 gap-3">
                    <div className="text-center">
                      <p className="text-lg font-bold text-text-primary">{passRate(run)}%</p>
                      <p className="text-xs text-text-muted">Pass Rate</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-text-primary">{run.total}</p>
                      <p className="text-xs text-text-muted">Total Tests</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-status-success">{run.passed}</p>
                      <p className="text-xs text-text-muted">Passed</p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-status-error">{run.failed + run.skipped}</p>
                      <p className="text-xs text-text-muted">Issues</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
