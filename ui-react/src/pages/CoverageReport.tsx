import { useState } from 'react'
import { listS3Objects, getS3Object } from '../lib/aws'

interface ComponentCoverage {
  component: string
  coverage_percentage: number
  tests_mapped: number
  pass_rate: number
  risk_score: number
  is_covered: boolean
}

interface CoverageData {
  tenant_id?: string
  run_id?: string
  generated_at?: string
  overall_coverage: number
  deployment_verdict: string
  verdict_reasoning?: string
  components: ComponentCoverage[]
}

/**
 * Normalize raw S3 coverage JSON (from coverage_risk_agent) into our CoverageData shape.
 * The agent writes: { metrics: { overall_coverage_pct }, component_coverage: {...}, ai_analysis: { deployment_verdict, verdict_rationale } }
 */
function normalizeCoverageData(raw: Record<string, unknown>): CoverageData {
  const metrics = (raw.metrics ?? {}) as Record<string, unknown>
  const aiAnalysis = (raw.ai_analysis ?? {}) as Record<string, unknown>
  const compCoverage = (raw.component_coverage ?? {}) as Record<string, Record<string, unknown>>

  const components: ComponentCoverage[] = Object.entries(compCoverage).map(([name, data]) => ({
    component: name,
    coverage_percentage: data.test_count ? ((data.pass_rate as number) ?? 0) : 0,
    tests_mapped: (data.test_count as number) ?? 0,
    pass_rate: (data.pass_rate as number) ?? 0,
    risk_score: (data.risk_score as number) ?? 0,
    is_covered: (data.is_covered as boolean) ?? false,
  }))

  return {
    tenant_id: raw.tenant_id as string | undefined,
    generated_at: raw.generated_at as string | undefined,
    overall_coverage: (metrics.overall_coverage_pct as number) ?? 0,
    deployment_verdict: (aiAnalysis.deployment_verdict as string) ?? (raw.deployment_verdict as string) ?? 'unknown',
    verdict_reasoning: (aiAnalysis.verdict_rationale as string) ?? undefined,
    components,
  }
}

export default function CoverageReport() {
  const [tenantId, setTenantId] = useState('demo-ecommerce')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [report, setReport] = useState<CoverageData | null>(null)

  async function loadReport() {
    setLoading(true)
    setError(null)
    setReport(null)
    try {
      // Try to find coverage reports in S3
      const objects = await listS3Objects(`${tenantId}/coverage/`, 20)
      const jsonFiles = objects.filter(o => o.Key?.endsWith('.json'))

      if (jsonFiles.length === 0) {
        // Try alternative path
        const alt = await listS3Objects(`${tenantId}/reports/coverage`, 20)
        const altJson = alt.filter(o => o.Key?.endsWith('.json'))
        if (altJson.length === 0) {
          setError('No coverage reports found for this tenant. Run the Coverage & Risk agent first.')
          return
        }
        // Load the latest one
        const latest = altJson[altJson.length - 1]!
        const data = await getS3Object<Record<string, unknown>>(latest.Key!)
        if (data) setReport(normalizeCoverageData(data))
        return
      }

      // Load the latest report
      const latest = jsonFiles[jsonFiles.length - 1]!
      const data = await getS3Object<Record<string, unknown>>(latest.Key!)
      if (data) {
        setReport(normalizeCoverageData(data))
      } else {
        setError('Failed to parse coverage report.')
      }
    } catch (err) {
      setError(`Failed to load coverage report: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">📈 Coverage Report</h1>
      <p className="text-gray-600 dark:text-gray-400">
        Per-component test coverage and deployment verdicts from the Coverage & Risk agent
      </p>

      {/* Load Form */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
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
            onClick={loadReport}
            disabled={loading}
            className="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? '⏳ Loading...' : '📈 Load Coverage Report'}
          </button>
        </div>
        {error && <p className="text-red-600 dark:text-red-400 text-sm mt-3">{error}</p>}
      </div>

      {/* Report Display */}
      {report && (
        <div className="space-y-6">
          {/* Deployment Verdict */}
          <VerdictBanner verdict={report.deployment_verdict} reasoning={report.verdict_reasoning} />

          {/* Overall Coverage */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold mb-3">Overall Coverage</h2>
            <div className="flex items-center gap-4">
              <div className="flex-1">
                <div className="w-full h-4 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all ${getCoverageColor(report.overall_coverage ?? 0)}`}
                    style={{ width: `${Math.min(report.overall_coverage ?? 0, 100)}%` }}
                  />
                </div>
              </div>
              <span className="text-2xl font-bold">{(report.overall_coverage ?? 0).toFixed(1)}%</span>
            </div>
            {report.generated_at && (
              <p className="text-xs text-gray-500 mt-2">
                Generated: {new Date(report.generated_at).toLocaleString()}
              </p>
            )}
          </div>

          {/* Per-Component Coverage */}
          <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
            <h2 className="text-lg font-semibold mb-4">Per-Component Coverage</h2>
            <div className="space-y-4">
              {report.components.map((comp) => (
                <ComponentRow key={comp.component} component={comp} />
              ))}
              {report.components.length === 0 && (
                <p className="text-sm text-gray-500">No component-level data available.</p>
              )}
            </div>
          </div>
        </div>
      )}

      {!report && !loading && !error && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          Enter your Tenant ID and click "Load Coverage Report" to view coverage data.
        </p>
      )}
    </div>
  )
}

function VerdictBanner({ verdict, reasoning }: { verdict: string; reasoning?: string }) {
  const config = getVerdictConfig(verdict)

  return (
    <div className={`rounded-lg p-6 border ${config.borderCls} ${config.bgCls}`}>
      <div className="flex items-center gap-3">
        <span className="text-3xl">{config.icon}</span>
        <div>
          <h3 className={`text-lg font-bold ${config.textCls}`}>{config.label}</h3>
          <p className={`text-sm ${config.subtextCls}`}>
            {reasoning || config.defaultReasoning}
          </p>
        </div>
      </div>
    </div>
  )
}

function ComponentRow({ component }: { component: ComponentCoverage }) {
  const pct = component.coverage_percentage ?? 0

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium">{component.component}</span>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">
            {component.tests_mapped ?? 0} tests • pass rate: {(component.pass_rate ?? 0).toFixed(0)}% • risk: {(component.risk_score ?? 0).toFixed(0)}
          </span>
          <span className="font-medium w-14 text-right">{pct.toFixed(0)}%</span>
        </div>
      </div>
      <div className="w-full h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${getCoverageColor(pct)}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      {component.risk_score > 70 && (
        <p className="text-xs text-red-500">High Risk: {component.risk_score.toFixed(0)}/100</p>
      )}
    </div>
  )
}

function getCoverageColor(pct: number): string {
  if (pct >= 80) return 'bg-green-500'
  if (pct >= 50) return 'bg-yellow-500'
  return 'bg-red-500'
}

function getVerdictConfig(verdict: string) {
  switch (verdict) {
    case 'safe_to_deploy':
      return {
        icon: '✅',
        label: 'Safe to Deploy',
        borderCls: 'border-green-200 dark:border-green-800',
        bgCls: 'bg-green-50 dark:bg-green-900/20',
        textCls: 'text-green-800 dark:text-green-200',
        subtextCls: 'text-green-600 dark:text-green-400',
        defaultReasoning: 'All components have adequate test coverage. Deployment is safe to proceed.',
      }
    case 'deploy_with_caution':
      return {
        icon: '⚠️',
        label: 'Deploy with Caution',
        borderCls: 'border-yellow-200 dark:border-yellow-800',
        bgCls: 'bg-yellow-50 dark:bg-yellow-900/20',
        textCls: 'text-yellow-800 dark:text-yellow-200',
        subtextCls: 'text-yellow-600 dark:text-yellow-400',
        defaultReasoning: 'Some components have gaps in coverage. Deploy with monitoring enabled.',
      }
    case 'do_not_deploy':
      return {
        icon: '🛑',
        label: 'Do Not Deploy',
        borderCls: 'border-red-200 dark:border-red-800',
        bgCls: 'bg-red-50 dark:bg-red-900/20',
        textCls: 'text-red-800 dark:text-red-200',
        subtextCls: 'text-red-600 dark:text-red-400',
        defaultReasoning: 'Critical coverage gaps detected. Deployment is not recommended.',
      }
    default:
      return {
        icon: '❓',
        label: verdict || 'Unknown',
        borderCls: 'border-gray-200 dark:border-gray-700',
        bgCls: 'bg-gray-50 dark:bg-gray-800',
        textCls: 'text-gray-800 dark:text-gray-200',
        subtextCls: 'text-gray-600 dark:text-gray-400',
        defaultReasoning: 'Verdict could not be determined.',
      }
  }
}
