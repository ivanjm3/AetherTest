import { useState } from 'react'
import { listS3Objects, getS3Object } from '../lib/aws'

interface FailedTest {
  test_name: string
  test_id?: string
  component?: string
  failure_reason: string
  failure_type?: string
  evidence?: Record<string, unknown>
}

interface ExecutionResult {
  test_name: string
  test_id?: string
  status: string
  component?: string
  duration_ms?: number
  evidence?: Record<string, unknown>
}

interface ExecutionData {
  execution_id?: string
  tenant_id?: string
  summary: {
    total: number
    passed: number
    failed: number
    pass_rate: number
    self_healed?: number
  }
  failed_tests: FailedTest[]
  results: ExecutionResult[]
}

export default function TestResults() {
  const [tenantId, setTenantId] = useState('demo-ecommerce')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [execKeys, setExecKeys] = useState<string[]>([])
  const [selectedKey, setSelectedKey] = useState('')
  const [data, setData] = useState<ExecutionData | null>(null)
  const [loadingData, setLoadingData] = useState(false)

  async function findResults() {
    setLoading(true)
    setError(null)
    setData(null)
    setExecKeys([])
    try {
      const objects = await listS3Objects(`${tenantId}/executor-results/`, 50)
      const altObjects = await listS3Objects(`${tenantId}/test-results/`, 50)
      const all = [...objects, ...altObjects].filter(o => o.Key?.endsWith('.json'))
      const keys = all.map(o => o.Key)
      setExecKeys(keys)
      if (keys.length === 0) {
        setError('No execution results found. Run demo.py or orchestrator.py first.')
      }
    } catch (err) {
      setError(`Failed to find results: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  async function loadResults() {
    if (!selectedKey) return
    setLoadingData(true)
    setData(null)
    try {
      const raw = await getS3Object<ExecutionData>(selectedKey)
      if (raw) setData(raw)
      else setError('Failed to parse results file.')
    } catch (err) {
      setError(`Failed to load: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoadingData(false)
    }
  }

  const summary = data?.summary
  const failedTests = data?.failed_tests ?? []
  const allResults = data?.results ?? []

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">📊 Test Results</h1>
      <p className="text-gray-600 dark:text-gray-400">
        View test execution results and pass/fail breakdown
      </p>

      {/* Search */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="block text-sm font-medium mb-1">Tenant ID</label>
            <input
              type="text"
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
              value={tenantId}
              onChange={e => setTenantId(e.target.value)}
              placeholder="e.g. demo-ecommerce"
            />
          </div>
          <button
            onClick={findResults}
            disabled={loading}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '⏳...' : '🔍 Find Results'}
          </button>
        </div>

        {error && <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>}

        {execKeys.length > 0 && (
          <>
            <p className="text-sm text-green-600 dark:text-green-400">Found {execKeys.length} result file(s)</p>
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium mb-1">Select Execution</label>
                <select
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
                  value={selectedKey}
                  onChange={e => setSelectedKey(e.target.value)}
                >
                  <option value="">-- Select --</option>
                  {execKeys.map(k => (
                    <option key={k} value={k}>{k}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={loadResults}
                disabled={!selectedKey || loadingData}
                className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {loadingData ? '⏳...' : 'Load'}
              </button>
            </div>
          </>
        )}
      </div>

      {/* Summary */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <MetricCard label="Total Tests" value={String(summary.total)} />
          <MetricCard label="Passed" value={String(summary.passed)} color="green" />
          <MetricCard label="Failed" value={String(summary.failed)} color="red" />
          <MetricCard label="Pass Rate" value={`${summary.pass_rate}%`} color={summary.pass_rate >= 80 ? 'green' : 'red'} />
          {summary.self_healed != null && summary.self_healed > 0 && (
            <MetricCard label="Self-Healed" value={String(summary.self_healed)} color="green" />
          )}
        </div>
      )}

      {/* Failed Tests */}
      {failedTests.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold text-red-700 dark:text-red-400">❌ Failed Tests ({failedTests.length})</h2>
          {failedTests.map((ft, i) => (
            <div key={ft.test_id ?? i} className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 space-y-2">
              <p className="font-medium text-red-800 dark:text-red-300">{ft.test_name}</p>
              {ft.component && <p className="text-xs text-red-600 dark:text-red-400">Component: {ft.component}</p>}
              <p className="text-sm text-red-700 dark:text-red-400">Reason: {ft.failure_reason}</p>
              {ft.failure_type && <p className="text-xs text-red-500">Type: {ft.failure_type}</p>}
            </div>
          ))}
        </section>
      )}

      {/* All Results */}
      {allResults.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">All Test Results</h2>
          <div className="space-y-2">
            {allResults.map((r, i) => {
              const icon = r.status === 'passed' ? '✅' : r.status === 'failed' ? '❌' : '⊘'
              return (
                <div key={r.test_id ?? i} className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center gap-3">
                  <span>{icon}</span>
                  <span className="flex-1 text-sm font-medium">{r.test_name}</span>
                  {r.component && <span className="text-xs text-gray-500">{r.component}</span>}
                  <span className={`text-xs font-medium uppercase ${r.status === 'passed' ? 'text-green-600' : r.status === 'failed' ? 'text-red-600' : 'text-gray-500'}`}>
                    {r.status}
                  </span>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {!data && !loading && !error && execKeys.length === 0 && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Enter Tenant ID and click "Find Results". Use <code>demo-ecommerce</code> for demo run.
        </p>
      )}
    </div>
  )
}

function MetricCard({ label, value, color }: { label: string; value: string; color?: string }) {
  const colorCls = color === 'green'
    ? 'text-green-600 dark:text-green-400'
    : color === 'red'
      ? 'text-red-600 dark:text-red-400'
      : ''

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
      <p className={`text-xl font-bold mt-1 ${colorCls}`}>{value}</p>
    </div>
  )
}
