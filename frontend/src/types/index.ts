// Job configuration types
export type JobType = 'step_function' | 'airflow' | 'metadata'

export interface JobConfig {
  type: JobType
  path: string // ARN, DAG path, or metadata JSON
  name?: string
}

export interface Dependency {
  id: string
  label: string
  type: 'source' | 'target' | 'connection'
  value: string
  editable: boolean
  selected: boolean
  sourceArn?: string  // which ARN/input this dependency came from
}

// Test case types
export interface TestCase {
  id: string
  name: string
  category: 'row_count' | 'schema' | 'null_check' | 'transform' | 'referential_integrity' | 'freshness' | 'custom'
  description: string
  user_story: string
  sql: string
  expected: string
  priority: 'high' | 'medium' | 'low'
}

// Execution types
export interface TestResult {
  test_id: string
  test_name: string
  description: string
  status: 'passed' | 'failed' | 'skipped' | 'error'
  actual: string
  expected: string
  duration_ms: number
  error_message?: string
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

export interface AnalysisSummary {
  total_failures: number
  real_defects: number
  false_positives: number
  regressions?: number
  environment_issues?: number
}

export interface ExecutionRun {
  id: string
  timestamp: string
  total: number
  passed: number
  failed: number
  errors?: number
  skipped: number
  results: TestResult[]
  analysis?: {
    analyses: FailureAnalysis[]
    summary: AnalysisSummary
    requires_immediate_attention: FailureAnalysis[]
  }
}

// Query validator types
export type QueryMode = 'nlp' | 'sql'

export interface QueryResult {
  generated_sql: string
  columns: string[]
  rows: Record<string, unknown>[]
  row_count: number
  execution_time_ms: number
}

// Log types
export interface LogEntry {
  id: string
  timestamp: string
  level: 'info' | 'success' | 'error' | 'warning'
  message: string
}

// App state
export type ActiveTab = 'run-tests' | 'query-validator' | 'results'
export type RunTestStep = 1 | 2 | 3
