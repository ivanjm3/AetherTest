import { useState } from 'react'
import { listS3Objects, getS3Object } from '../lib/aws'

interface S3Object {
  Key?: string
  LastModified?: string
  Size?: number
}

interface TestCase {
  test_id: string
  test_name: string
  test_type: string
  priority: string
  description: string
  given: string[]
  when: string[]
  then: string[]
  component: string
  requirement_ref: string
  tags: string[]
}

interface TestSuite {
  suite_id?: string
  test_suite_id?: string
  generated_at?: string
  authored_at?: string
  total_test_cases?: number
  total_tests?: number
  test_cases: TestCase[]
}

export default function TestCases() {
  const [tenantId, setTenantId] = useState('demo-ecommerce')
  const [objects, setObjects] = useState<S3Object[]>([])
  const [loading, setLoading] = useState(false)
  const [selectedKey, setSelectedKey] = useState<string>('')
  const [suite, setSuite] = useState<TestSuite | null>(null)
  const [loadingSuite, setLoadingSuite] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function findTestCases() {
    setLoading(true)
    setError(null)
    setSuite(null)
    try {
      const results = await listS3Objects(`${tenantId}/test-cases/`, 50)
      const authored = await listS3Objects(`${tenantId}/authored-tests/`, 50)
      const all = [...results, ...authored].filter(o => o.Key?.endsWith('.json'))
      setObjects(all)
      if (all.length === 0) {
        setError('No test case files found for this tenant.')
      }
    } catch (err) {
      setError(`Failed to list test cases: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  async function loadSuite() {
    if (!selectedKey) return
    setLoadingSuite(true)
    setSuite(null)
    try {
      const data = await getS3Object<TestSuite>(selectedKey)
      if (data) {
        setSuite(data)
      } else {
        setError('Failed to load test suite.')
      }
    } catch (err) {
      setError(`Failed to load suite: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoadingSuite(false)
    }
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">📋 Test Cases</h1>
      <p className="text-gray-600 dark:text-gray-400">Browse generated test cases from S3</p>

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
            onClick={findTestCases}
            disabled={loading}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '⏳...' : '🔍 Find Test Cases'}
          </button>
        </div>

        {error && <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>}

        {objects.length > 0 && (
          <>
            <p className="text-sm text-green-600 dark:text-green-400">Found {objects.length} test case file(s)</p>
            <div className="flex gap-3 items-end">
              <div className="flex-1">
                <label className="block text-sm font-medium mb-1">Select Test Suite</label>
                <select
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
                  value={selectedKey}
                  onChange={e => setSelectedKey(e.target.value)}
                >
                  <option value="">-- Select --</option>
                  {objects.map(obj => (
                    <option key={obj.Key} value={obj.Key}>{obj.Key}</option>
                  ))}
                </select>
              </div>
              <button
                onClick={loadSuite}
                disabled={!selectedKey || loadingSuite}
                className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {loadingSuite ? '⏳...' : 'Load'}
              </button>
            </div>
          </>
        )}
      </div>

      {/* Suite Display */}
      {suite && (
        <section className="space-y-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <p className="text-sm"><strong>Suite ID:</strong> {suite.suite_id ?? suite.test_suite_id ?? 'N/A'}</p>
            <p className="text-sm"><strong>Generated At:</strong> {suite.generated_at ?? suite.authored_at ?? 'N/A'}</p>
            <p className="text-sm"><strong>Total Tests:</strong> {suite.total_test_cases ?? suite.total_tests ?? suite.test_cases.length}</p>
          </div>

          <div className="space-y-3">
            {suite.test_cases.slice(0, 20).map((tc, i) => (
              <TestCaseCard key={tc.test_id ?? i} tc={tc} index={i + 1} />
            ))}
          </div>
        </section>
      )}

      {!objects.length && !loading && !error && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Enter your Tenant ID above and click "Find Test Cases". Use <code>demo-ecommerce</code> for the demo run.
        </p>
      )}
    </div>
  )
}

function TestCaseCard({ tc, index }: { tc: TestCase; index: number }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 text-left flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        aria-expanded={open}
      >
        <span className="font-medium text-sm">Test {index}: {tc.test_name || 'Unknown'}</span>
        <span className="ml-auto text-gray-400">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 text-sm border-t border-gray-100 dark:border-gray-700 pt-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              {tc.given?.length > 0 && (
                <>
                  <p className="font-semibold text-green-700 dark:text-green-400">Given:</p>
                  <ul className="list-disc list-inside text-gray-600 dark:text-gray-400">{tc.given.map((g, j) => <li key={j}>{g}</li>)}</ul>
                </>
              )}
              {tc.when?.length > 0 && (
                <>
                  <p className="font-semibold text-blue-700 dark:text-blue-400 mt-2">When:</p>
                  <ul className="list-disc list-inside text-gray-600 dark:text-gray-400">{tc.when.map((w, j) => <li key={j}>{w}</li>)}</ul>
                </>
              )}
            </div>
            <div>
              {tc.then?.length > 0 && (
                <>
                  <p className="font-semibold text-purple-700 dark:text-purple-400">Then:</p>
                  <ul className="list-disc list-inside text-gray-600 dark:text-gray-400">{tc.then.map((t, j) => <li key={j}>{t}</li>)}</ul>
                </>
              )}
            </div>
          </div>
          {tc.tags?.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {tc.tags.map(tag => (
                <span key={tag} className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-xs">{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
