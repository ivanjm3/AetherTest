import { useState } from 'react'

interface Requirement {
  id: string
  type: string
  content: string
  component: string
}

interface TestCase {
  test_id: string
  test_name: string
  requirement_ref: string
  test_type: string
  priority: string
  description: string
  given: string[]
  when: string[]
  then: string[]
  tags: string[]
  acceptance_criteria: string
}

interface AuthorResult {
  statusCode: number
  suite_id: string
  total_tests_authored: number
  requirements_processed: number
  s3_key: string
  test_suite: {
    test_cases: TestCase[]
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export default function Requirements() {
  const [appName, setAppName] = useState('My Application')
  const [appVersion, setAppVersion] = useState('1.0.0')
  const [tenantId, setTenantId] = useState('my-tenant')
  const [componentsText, setComponentsText] = useState('Login Page\nDashboard\nCheckout\nPayment Service')
  const [requirements, setRequirements] = useState<Requirement[]>([
    { id: 'REQ-001', type: 'user_story', content: 'As a customer, I want to log in with my email and password so that I can access my account securely', component: 'Login Page' },
    { id: 'REQ-002', type: 'user_story', content: 'As a customer, I want to add items to my shopping cart so that I can purchase multiple products at once', component: 'Checkout' },
    { id: 'REQ-003', type: 'acceptance_criteria', content: 'Payment processing must complete within 5 seconds and display a confirmation number to the user', component: 'Payment Service' },
  ])
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<AuthorResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [typeFilter, setTypeFilter] = useState<string[]>(['functional', 'security', 'performance', 'usability'])

  const components = componentsText.split('\n').map(c => c.trim()).filter(Boolean)

  function addRequirement() {
    const n = requirements.length + 1
    setRequirements([...requirements, { id: `REQ-${String(n).padStart(3, '0')}`, type: 'user_story', content: '', component: '' }])
  }

  function removeRequirement(index: number) {
    setRequirements(requirements.filter((_, i) => i !== index))
  }

  function updateRequirement(index: number, field: keyof Requirement, value: string) {
    setRequirements(requirements.map((r, i) => i === index ? { ...r, [field]: value } : r))
  }

  async function generate() {
    const validReqs = requirements.filter(r => r.content.trim())
    if (validReqs.length === 0) {
      setError('Please write at least one requirement before generating.')
      return
    }

    setLoading(true)
    setError(null)
    setResult(null)

    try {
      const payload = {
        tenant_id: tenantId,
        requirements: validReqs,
        aut_context: {
          name: appName,
          version: appVersion,
          components,
        },
      }
      const response = await fetch(`${API_BASE}/api/test-author`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      const res: AuthorResult = await response.json()
      if (response.ok && res.statusCode === 200) {
        setResult(res)
      } else {
        setError(`Generation failed: ${(res as unknown as Record<string, unknown>).error ?? `status ${res.statusCode}`}`)
      }
    } catch (err) {
      setError(`Generation failed: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  const testCases = result?.test_suite?.test_cases ?? []
  const filteredCases = testCases.filter(tc => typeFilter.includes(tc.test_type || 'functional'))

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">✍️ Write Requirements</h1>
      <p className="text-gray-600 dark:text-gray-400">
        Describe your application and requirements in plain English. Claude will generate BDD test cases automatically.
      </p>

      {/* Step 1: App Details */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <h2 className="text-lg font-semibold">Step 1: Your Application</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <InputField label="Application Name" value={appName} onChange={setAppName} placeholder="e.g. E-Commerce Platform" />
          <InputField label="Version" value={appVersion} onChange={setAppVersion} placeholder="e.g. 2.1.0" />
          <InputField label="Tenant ID" value={tenantId} onChange={setTenantId} placeholder="e.g. belron-uat" />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Components (one per line)</label>
          <textarea
            className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            rows={4}
            value={componentsText}
            onChange={e => setComponentsText(e.target.value)}
          />
          {components.length > 0 && (
            <p className="text-xs text-gray-500 mt-1">Detected {components.length} components: {components.join(', ')}</p>
          )}
        </div>
      </section>

      {/* Step 2: Requirements */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <h2 className="text-lg font-semibold">Step 2: Write Your Requirements</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Write each requirement in plain English. Use user stories, acceptance criteria, or business language.
        </p>

        {requirements.map((req, i) => (
          <div key={i} className="border border-gray-200 dark:border-gray-600 rounded-md p-4 space-y-3">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-3 items-end">
              <InputField label="ID" value={req.id} onChange={v => updateRequirement(i, 'id', v)} />
              <div>
                <label className="block text-sm font-medium mb-1">Type</label>
                <select
                  className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
                  value={req.type}
                  onChange={e => updateRequirement(i, 'type', e.target.value)}
                >
                  <option value="user_story">User Story</option>
                  <option value="acceptance_criteria">Acceptance Criteria</option>
                  <option value="business_rule">Business Rule</option>
                </select>
              </div>
              <InputField label="Component" value={req.component} onChange={v => updateRequirement(i, 'component', v)} placeholder="e.g. Login Page" />
              <button
                onClick={() => removeRequirement(i)}
                className="px-3 py-2 text-sm rounded-md bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 hover:bg-red-100 dark:hover:bg-red-900/50 transition-colors"
                aria-label={`Remove requirement ${req.id}`}
              >
                🗑️ Remove
              </button>
            </div>
            <textarea
              className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500"
              rows={3}
              value={req.content}
              onChange={e => updateRequirement(i, 'content', e.target.value)}
              placeholder="Describe the requirement in plain English..."
            />
          </div>
        ))}

        <button
          onClick={addRequirement}
          className="px-4 py-2 text-sm rounded-md border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
        >
          ➕ Add Another Requirement
        </button>
      </section>

      {/* Step 3: Generate */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700 space-y-4">
        <h2 className="text-lg font-semibold">Step 3: Generate Test Cases with AI</h2>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Claude will read your {requirements.filter(r => r.content.trim()).length} requirement(s) and generate complete BDD test cases with Given / When / Then steps.
        </p>
        <button
          onClick={generate}
          disabled={loading}
          className="w-full py-3 rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? '⏳ Generating...' : '🤖 Generate Test Cases with Claude'}
        </button>
        {error && <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>}
      </section>

      {/* Results */}
      {result && (
        <section className="space-y-4">
          <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
            <p className="text-green-800 dark:text-green-200 font-medium">
              ✅ Claude generated {result.total_tests_authored} BDD test cases for {appName}
            </p>
            {result.s3_key && (
              <p className="text-sm text-green-600 dark:text-green-400 mt-1">Saved to S3: {result.s3_key}</p>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetricCard label="Tests Generated" value={String(result.total_tests_authored)} />
            <MetricCard label="High Priority" value={String(testCases.filter(tc => tc.priority === 'high').length)} />
            <MetricCard label="Medium Priority" value={String(testCases.filter(tc => tc.priority === 'medium').length)} />
            <MetricCard label="Low Priority" value={String(testCases.filter(tc => tc.priority === 'low').length)} />
          </div>

          {/* Filter */}
          <div className="flex gap-2 flex-wrap">
            {['functional', 'security', 'performance', 'usability'].map(type => (
              <label key={type} className="flex items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={typeFilter.includes(type)}
                  onChange={e => {
                    if (e.target.checked) setTypeFilter([...typeFilter, type])
                    else setTypeFilter(typeFilter.filter(t => t !== type))
                  }}
                />
                {type}
              </label>
            ))}
          </div>

          {/* Test Cases List */}
          <div className="space-y-3">
            {filteredCases.map((tc, i) => (
              <TestCaseCard key={tc.test_id || i} tc={tc} index={i + 1} />
            ))}
            {filteredCases.length === 0 && (
              <p className="text-sm text-gray-500">No test cases match the selected filter.</p>
            )}
          </div>
        </section>
      )}
    </div>
  )
}

function InputField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium mb-1">{label}</label>
      <input
        type="text"
        className="w-full rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700">
      <p className="text-sm text-gray-500 dark:text-gray-400">{label}</p>
      <p className="text-xl font-bold mt-1">{value}</p>
    </div>
  )
}

function TestCaseCard({ tc, index }: { tc: TestCase; index: number }) {
  const [open, setOpen] = useState(false)
  const priorityIcon = tc.priority === 'high' ? '🔴' : tc.priority === 'medium' ? '🟡' : '🟢'

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full px-4 py-3 text-left flex items-center gap-2 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors"
        aria-expanded={open}
      >
        <span>{priorityIcon}</span>
        <span className="font-medium text-sm">Test {index}: {tc.test_name}</span>
        <span className="ml-auto text-xs px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 uppercase">
          {tc.test_type}
        </span>
        <span className="text-gray-400">{open ? '▼' : '▶'}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3 text-sm border-t border-gray-100 dark:border-gray-700 pt-3">
          <p className="text-gray-500">
            <strong>ID:</strong> {tc.test_id} | <strong>Priority:</strong> {tc.priority.toUpperCase()} | <strong>Requirement:</strong> {tc.requirement_ref}
          </p>
          {tc.description && <p className="text-gray-600 dark:text-gray-400"><strong>Description:</strong> {tc.description}</p>}
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
              {tc.acceptance_criteria && (
                <p className="mt-2 text-gray-600 dark:text-gray-400"><strong>Acceptance Criteria:</strong> {tc.acceptance_criteria}</p>
              )}
            </div>
          </div>
          {tc.tags?.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {tc.tags.map(tag => (
                <span key={tag} className="px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-xs text-gray-600 dark:text-gray-400">{tag}</span>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
