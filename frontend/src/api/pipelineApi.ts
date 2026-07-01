import type { JobConfig, Dependency, TestCase, ExecutionRun } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001'

interface AnalyzeJobResponse {
  job_name: string
  dependencies: Omit<Dependency, 'selected'>[]
}

interface GenerateTestsResponse {
  test_cases: TestCase[]
}

interface RunTestsResponse {
  execution: ExecutionRun
}

export async function analyzeJob(config: JobConfig, fileContent?: string): Promise<AnalyzeJobResponse> {
  const res = await fetch(`${API_BASE}/api/analyze-job`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...config, file_content: fileContent ?? null }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || err.error || `Failed to analyze job: ${res.status}`)
  }
  return res.json()
}

export async function generateTests(
  config: JobConfig,
  dependencies: Dependency[],
  forceRegenerate: boolean = false
): Promise<GenerateTestsResponse> {
  const res = await fetch(`${API_BASE}/api/generate-tests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_config: config, dependencies, force_regenerate: forceRegenerate }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    throw new Error(err.error || `Failed to generate tests: ${res.status}`)
  }
  return res.json()
}

export async function runTests(
  config: JobConfig,
  dependencies: Dependency[],
  testCases: TestCase[]
): Promise<RunTestsResponse> {
  const res = await fetch(`${API_BASE}/api/run-tests`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ job_config: config, dependencies, test_cases: testCases }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    throw new Error(err.error || `Failed to run tests: ${res.status}`)
  }
  return res.json()
}

export async function fetchResults(): Promise<ExecutionRun[]> {
  const res = await fetch(`${API_BASE}/api/results`)
  if (!res.ok) {
    throw new Error(`Failed to fetch results: ${res.status}`)
  }
  return res.json()
}

export interface FailureAnalysis {
  failure_id: string
  test_name: string
  component: string
  classification: 'application_defect' | 'test_data_issue' | 'environment_instability' | 'regression'
  confidence: number
  root_cause_hypothesis: string
  is_false_positive: boolean
  recommended_action: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  fix_suggestion: string
}

export interface AnalyzeFailuresResponse {
  analyses: FailureAnalysis[]
  summary: {
    total_failures: number
    real_defects: number
    false_positives: number
    regressions?: number
    environment_issues?: number
  }
  requires_immediate_attention: FailureAnalysis[]
}

export async function analyzeFailures(
  executionId: string,
  failedTests: Array<Record<string, unknown>>,
  recentChanges: string[] = []
): Promise<AnalyzeFailuresResponse> {
  const res = await fetch(`${API_BASE}/api/analyze-failures`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      execution_id: executionId,
      failed_tests: failedTests,
      recent_changes: recentChanges,
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }))
    throw new Error(err.detail || `Failed to analyze failures: ${res.status}`)
  }
  return res.json()
}
