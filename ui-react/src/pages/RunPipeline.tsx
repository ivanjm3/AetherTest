import { useState } from 'react'

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

interface Component {
  component_id: string
  name: string
  component_type: string
  dependencies: string[]
  api_surface: string[]
  ui_entry_points: string[]
  metadata: { criticality: string }
}

interface Requirement {
  id: string
  type: string
  content: string
  component: string
}

interface PipelineResult {
  execution_id: string
  tenant_id: string
  started_at: string
  completed_at: string
  final_verdict: {
    deployment_verdict: string
    pass_rate: number
    coverage_pct: number
    real_defects: number
    critical_gaps: number
    recommendations: Array<{ action: string } | string>
  }
  steps: Record<string, unknown>
}

export default function RunPipeline() {
  const [tenantId, setTenantId] = useState('my-org')
  const [autId, setAutId] = useState('hello-fastapi')
  const [autVersion, setAutVersion] = useState('1.0.0')
  const [componentsJson, setComponentsJson] = useState<string>(
    JSON.stringify(
      [
        {
          component_id: 'hello-endpoint',
          name: 'Hello World API',
          component_type: 'api_endpoint',
          dependencies: [],
          api_surface: ['/', '/hello'],
          ui_entry_points: [],
          metadata: { criticality: 'high' },
        },
      ],
      null,
      2
    )
  )
  const [requirements, setRequirements] = useState<Requirement[]>([
    {
      id: 'REQ-001',
      type: 'user_story',
      content: 'As a user, I want to call GET / and receive a Hello World JSON response',
      component: 'Hello World API',
    },
  ])
  const [fastMode, setFastMode] = useState(true)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<PipelineResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [logs, setLogs] = useState<string[]>([])

  function addRequirement() {
    const n = requirements.length + 1
    setRequirements([
      ...requirements,
      { id: `REQ-${String(n).padStart(3, '0')}`, type: 'user_story', content: '', component: '' },
    ])
  }

  function removeRequirement(index: number) {
    setRequirements(requirements.filter((_, i) => i !== index))
  }

  function updateRequirement(index: number, field: keyof Requirement, value: string) {
    setRequirements(requirements.map((r, i) => (i === index ? { ...r, [field]: value } : r)))
  }

  async function runPipeline() {
    setLoading(true)
    setError(null)
    setResult(null)
    setLogs(['Starting pipeline...'])

    try {
      let components: Component[]
      try {
        components = JSON.parse(componentsJson)
      } catch {
        setError('Invalid components JSON. Please fix the JSON syntax.')
        setLoading(false)
        return
      }

      const autConfig = {
        tenant_id: tenantId,
        aut_id: autId,
        aut_version: autVersion,
        aut_metadata: { components },
      }

      const validReqs = requirements.filter((r) => r.content.trim())

      setLogs((prev) => [...prev, `AUT: ${autId} v${autVersion} (${components.length} components)`])
      setLogs((prev) => [...prev, `Requirements: ${validReqs.length}`])
      setLogs((prev) => [...prev, `Mode: ${fastMode ? 'fast' : 'full'}`])
      setLogs((prev) => [...prev, 'Calling orchestrator...'])

      const payload: Record<string, unknown> = {
        aut_config: autConfig,
        fast_mode: fastMode,
      }
      if (validReqs.length > 0) {
        payload.requirements = validReqs
      }

      const response = await fetch(`${API_BASE}/api/run-pipeline`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      const res = await response.json()

      if (!response.ok) {
        setError(`Pipeline failed: ${res.error ?? `HTTP ${response.status}`}`)
        setLogs((prev) => [...prev, `ERROR: ${res.error}`])
      } else {
        setResult(res as PipelineResult)
        setLogs((prev) => [...prev, `Pipeline complete! Execution ID: ${res.execution_id}`])
        setLogs((prev) => [...prev, `Verdict: ${res.final_verdict?.deployment_verdict?.toUpperCase()}`])
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      setError(`Pipeline failed: ${msg}`)
      setLogs((prev) => [...prev, `ERROR: ${msg}`])
    } finally {
      setLoading(false)
    }
  }

  const verdict = result?.final_verdict
  const verdictColor =
    verdict?.deployment_verdict === 'safe_to_deploy'
      ? 'bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800'
      : verdict?.deployment_verdict === 'deploy_with_caution'
        ? 'bg-yellow-50 border-yellow-200 dark:bg-yellow-900/20 dark:border-yellow-800'
        : verdict?.deployment_verdict === 'do_not_deploy'
          ? 'bg-red-50 border-red-200 dark:bg-red-900/20 dark:border-red-800'
          : ''
  const verdictIcon =
    verdict?.deployment_verdict === 'safe_to_deploy'
      ? '🟢'
      : verdict?.deployment_verdict === 'deploy_with_caution'
        ? '🟡'
        : '🔴'

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">🚀 Run Pipeline</h1>
      <p className="text-gray-600 dark:text-gray-400">
        Configure your application, provide requirements, and run the full AetherTest pipeline from here.
      </p>

      {/* Step 1: AUT Config */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <h2 className="text-lg font-semibold">Step 1: Application Under Test</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium mb-1">Tenant ID</label>
            <input
              type="text"
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
              value={tenantId}
              onChange={(e) => setTenantId(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Application ID</label>
            <input
              type="text"
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
              value={autId}
              onChange={(e) => setAutId(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Version</label>
            <input
              type="text"
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
              value={autVersion}
              onChange={(e) => setAutVersion(e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Components (JSON array)</label>
          <textarea
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm font-mono"
            rows={10}
            value={componentsJson}
            onChange={(e) => setComponentsJson(e.target.value)}
          />
          <p className="text-xs text-gray-500 mt-1">
            Each component needs: component_id, name, component_type, dependencies, api_surface, ui_entry_points, metadata
          </p>
        </div>
      </section>

      {/* Step 2: Requirements */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <h2 className="text-lg font-semibold">Step 2: Requirements (optional)</h2>
        <p className="text-sm text-gray-500">
          Add requirements for BDD test generation. If empty, only AI-generated test cases will be used.
        </p>

        {requirements.map((req, i) => (
          <div key={i} className="border border-gray-200 dark:border-gray-600 rounded-md p-3 space-y-2">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-2 items-end">
              <div>
                <label className="block text-xs font-medium mb-1">ID</label>
                <input
                  type="text"
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1.5 text-sm"
                  value={req.id}
                  onChange={(e) => updateRequirement(i, 'id', e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Type</label>
                <select
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1.5 text-sm"
                  value={req.type}
                  onChange={(e) => updateRequirement(i, 'type', e.target.value)}
                >
                  <option value="user_story">User Story</option>
                  <option value="acceptance_criteria">Acceptance Criteria</option>
                  <option value="business_rule">Business Rule</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium mb-1">Component</label>
                <input
                  type="text"
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1.5 text-sm"
                  value={req.component}
                  onChange={(e) => updateRequirement(i, 'component', e.target.value)}
                />
              </div>
              <button
                onClick={() => removeRequirement(i)}
                className="px-2 py-1.5 text-sm rounded-md bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-100"
                aria-label={`Remove requirement ${req.id}`}
              >
                Remove
              </button>
            </div>
            <textarea
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-2 py-1.5 text-sm"
              rows={2}
              value={req.content}
              onChange={(e) => updateRequirement(i, 'content', e.target.value)}
              placeholder="Describe requirement in plain English..."
            />
          </div>
        ))}
        <button
          onClick={addRequirement}
          className="px-3 py-1.5 text-sm rounded-md border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700"
        >
          + Add Requirement
        </button>
      </section>

      {/* Step 3: Run */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <h2 className="text-lg font-semibold">Step 3: Run Pipeline</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={fastMode}
              onChange={(e) => setFastMode(e.target.checked)}
            />
            Fast mode (3 tests per component)
          </label>
        </div>
        <button
          onClick={runPipeline}
          disabled={loading}
          className="w-full py-3 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '⏳ Running Pipeline... (this takes 1-3 minutes)' : '🚀 Run Full Pipeline'}
        </button>
        {error && <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>}
      </section>

      {/* Logs */}
      {logs.length > 1 && (
        <section className="bg-gray-900 rounded-lg p-4 border border-gray-700">
          <h3 className="text-sm font-medium text-gray-400 mb-2">Pipeline Log</h3>
          <div className="font-mono text-xs text-green-400 space-y-0.5 max-h-48 overflow-y-auto">
            {logs.map((log, i) => (
              <div key={i}>{log}</div>
            ))}
            {loading && <div className="animate-pulse">▋</div>}
          </div>
        </section>
      )}

      {/* Results */}
      {verdict && (
        <section className="space-y-4">
          <div className={`rounded-lg p-6 border ${verdictColor}`}>
            <h2 className="text-xl font-bold mb-4">
              {verdictIcon} {verdict.deployment_verdict.replace(/_/g, ' ').toUpperCase()}
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-gray-500">Pass Rate</p>
                <p className="text-2xl font-bold">{verdict.pass_rate}%</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Coverage</p>
                <p className="text-2xl font-bold">{verdict.coverage_pct}%</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Real Defects</p>
                <p className="text-2xl font-bold">{verdict.real_defects}</p>
              </div>
              <div>
                <p className="text-sm text-gray-500">Critical Gaps</p>
                <p className="text-2xl font-bold">{verdict.critical_gaps}</p>
              </div>
            </div>
            {verdict.recommendations && verdict.recommendations.length > 0 && (
              <div className="mt-4">
                <p className="text-sm font-medium mb-2">Recommendations:</p>
                <ul className="list-disc list-inside text-sm text-gray-600 dark:text-gray-400 space-y-1">
                  {verdict.recommendations.map((rec, i) => (
                    <li key={i}>{typeof rec === 'string' ? rec : rec.action}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-500">
              Execution ID: <code className="text-xs">{result?.execution_id}</code>
            </p>
            <p className="text-sm text-gray-500 mt-1">
              View detailed results in <strong>Test Results</strong> and <strong>Coverage Report</strong> pages using tenant ID: <code>{result?.tenant_id}</code>
            </p>
          </div>
        </section>
      )}
    </div>
  )
}
