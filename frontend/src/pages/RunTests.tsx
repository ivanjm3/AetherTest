import { useState, useRef } from 'react'
import { useAppStore } from '@/store/appStore'
import { analyzeJob, generateTests, runTests, analyzeFailures } from '@/api/pipelineApi'
import StepIndicator from '@/components/StepIndicator'
import DependencyForm from '@/components/DependencyForm'
import TestCaseList from '@/components/TestCaseList'

/**
 * Auto-detect input type from content.
 * - arn:aws:states:... → step_function
 * - arn:aws:airflow:... → airflow
 * - Contains "import" or "DAG" or "airflow" → airflow
 * - Starts with { → step_function (ASL JSON) or metadata
 * - Otherwise → metadata
 */
function detectType(input: string): 'step_function' | 'airflow' | 'metadata' {
  const trimmed = input.trim()
  if (trimmed.startsWith('arn:aws:states:')) return 'step_function'
  if (trimmed.startsWith('arn:aws:airflow:')) return 'airflow'
  if (/\bimport\s+airflow\b/i.test(trimmed) || /\bDAG\b/.test(trimmed)) return 'airflow'
  if (trimmed.startsWith('{') && trimmed.includes('"States"')) return 'step_function'
  if (trimmed.startsWith('{')) return 'metadata'
  return 'metadata'
}

export default function RunTests() {
  const currentStep = useAppStore((s) => s.currentStep)
  const setCurrentStep = useAppStore((s) => s.setCurrentStep)
  const jobConfig = useAppStore((s) => s.jobConfig)
  const setJobConfig = useAppStore((s) => s.setJobConfig)
  const dependencies = useAppStore((s) => s.dependencies)
  const setDependencies = useAppStore((s) => s.setDependencies)
  const testCases = useAppStore((s) => s.testCases)
  const setTestCases = useAppStore((s) => s.setTestCases)
  const selectedTestIds = useAppStore((s) => s.selectedTestIds)
  const isLoadingJob = useAppStore((s) => s.isLoadingJob)
  const setIsLoadingJob = useAppStore((s) => s.setIsLoadingJob)
  const isGeneratingTests = useAppStore((s) => s.isGeneratingTests)
  const setIsGeneratingTests = useAppStore((s) => s.setIsGeneratingTests)
  const isRunningTests = useAppStore((s) => s.isRunningTests)
  const setIsRunningTests = useAppStore((s) => s.setIsRunningTests)
  const addExecutionRun = useAppStore((s) => s.addExecutionRun)
  const updateExecutionAnalysis = useAppStore((s) => s.updateExecutionAnalysis)
  const addLog = useAppStore((s) => s.addLog)
  const setActiveTab = useAppStore((s) => s.setActiveTab)

  const [jobPath, setJobPath] = useState(import.meta.env.VITE_DEFAULT_PIPELINE_ARN || '')
  const [fileContent, setFileContent] = useState<string | null>(null)
  const [fileName, setFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  // File upload handler
  function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (!file) return

    setFileName(file.name)
    const reader = new FileReader()
    reader.onload = (ev) => {
      const content = ev.target?.result as string
      setFileContent(content)
      if (!jobPath.trim()) {
        setJobPath(file.name)
      }
      addLog('info', `File loaded: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`)
    }
    reader.readAsText(file)
  }

  function clearFile() {
    setFileContent(null)
    setFileName(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  // Step 1: Load & Analyze (supports multiple inputs, one per line for ARNs)
  async function handleLoadJob() {
    const input = fileContent || jobPath.trim()
    if (!input) return

    setIsLoadingJob(true)
    addLog('info', 'Analyzing input...')

    try {
      // Split by newlines to detect multiple ARNs
      const lines = input.split('\n').map((l) => l.trim()).filter(Boolean)
      const arns = lines.filter((l) => l.startsWith('arn:aws:'))
      const nonArns = lines.filter((l) => !l.startsWith('arn:aws:'))

      let allDeps: Array<{ id: string; label: string; type: 'source' | 'target' | 'connection'; value: string; editable: boolean }> = []
      let jobName = ''

      if (arns.length > 0) {
        // Process each ARN separately
        for (const arn of arns) {
          const type = detectType(arn)
          addLog('info', `Analyzing: ${arn.slice(0, 60)}...`)
          const result = await analyzeJob({ type, path: arn })
          const tagged = result.dependencies.map((d) => ({ ...d, sourceArn: arn }))
          allDeps = [...allDeps, ...tagged]
          jobName = jobName ? `${jobName} + ${result.job_name}` : result.job_name
        }
      }

      if (nonArns.length > 0 || arns.length === 0) {
        // Treat remaining content as single input (code/JSON/description)
        const content = nonArns.length > 0 ? nonArns.join('\n') : input
        const type = detectType(content)
        addLog('info', `Detected type: ${type}`)
        const result = await analyzeJob({ type, path: content }, fileContent ?? undefined)
        const tagged = result.dependencies.map((d) => ({ ...d, sourceArn: content.slice(0, 60) }))
        allDeps = [...allDeps, ...tagged]
        jobName = jobName ? `${jobName} + ${result.job_name}` : result.job_name
      }

      // Deduplicate dependencies by value
      const seen = new Set<string>()
      const uniqueDeps = allDeps.filter((d) => {
        if (seen.has(d.value)) return false
        seen.add(d.value)
        return true
      })

      const detectedType = detectType(input)
      setJobConfig({ type: detectedType, path: input })
      setDependencies(uniqueDeps.map((d) => ({ ...d, selected: true })))
      setTestCases([])
      setCurrentStep(2)
      addLog('success', `Analyzed: "${jobName}" — ${uniqueDeps.length} unique dependencies found`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog('error', msg)
    } finally {
      setIsLoadingJob(false)
    }
  }

  // Step 2: Generate Tests (only selected dependencies)
  async function handleGenerateTests(forceRegenerate: boolean = false) {
    if (!jobConfig) return

    const selectedDeps = dependencies.filter((d) => d.selected)
    if (selectedDeps.length === 0) {
      addLog('warning', 'No dependencies selected. Select at least one to generate tests.')
      return
    }

    setIsGeneratingTests(true)
    addLog('info', forceRegenerate
      ? `Force regenerating tests for ${selectedDeps.length} dependencies...`
      : `Loading tests for ${selectedDeps.length} dependencies (cached if available)...`
    )

    try {
      const result = await generateTests(jobConfig, selectedDeps, forceRegenerate)
      setTestCases(result.test_cases)
      setCurrentStep(3)
      addLog('success', `${result.test_cases.length} test cases loaded`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog('error', msg)
    } finally {
      setIsGeneratingTests(false)
    }
  }

  // Step 3: Run Tests (only selected test cases)
  async function handleRunTests() {
    if (!jobConfig || testCases.length === 0) return

    const selectedDeps = dependencies.filter((d) => d.selected)
    const selectedTests = testCases.filter((tc) => selectedTestIds.has(tc.id))

    if (selectedTests.length === 0) {
      addLog('warning', 'No test cases selected. Select at least one to run.')
      return
    }

    setIsRunningTests(true)
    addLog('info', `Running ${selectedTests.length} selected tests via Athena...`)

    try {
      const result = await runTests(jobConfig, selectedDeps, selectedTests)
      addExecutionRun(result.execution)
      addLog(
        'success',
        `Tests complete: ${result.execution.passed}/${result.execution.total} passed`
      )

      // Auto-trigger failure analysis via test_analyst_agent if there are failures
      const failedResults = result.execution.results.filter(
        (r) => r.status === 'failed' || r.status === 'error'
      )
      if (failedResults.length > 0) {
        addLog('info', `Analyzing ${failedResults.length} failures with Test Analyst Agent...`)
        try {
          const analysis = await analyzeFailures(result.execution.id, failedResults as unknown as Array<Record<string, unknown>>)
          const summary = analysis.summary
          // Store analysis in execution run
          updateExecutionAnalysis(result.execution.id, analysis)
          addLog(
            'success',
            `Analysis complete: ${summary.real_defects} real defects, ${summary.false_positives} false positives`
          )
          if (analysis.requires_immediate_attention.length > 0) {
            addLog(
              'warning',
              `⚠️ ${analysis.requires_immediate_attention.length} critical issue(s) need immediate attention`
            )
          }
        } catch (analysisErr) {
          const msg = analysisErr instanceof Error ? analysisErr.message : String(analysisErr)
          addLog('warning', `Failure analysis skipped: ${msg}`)
        }
      }

      setActiveTab('results')
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err)
      addLog('error', msg)
    } finally {
      setIsRunningTests(false)
    }
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      {/* Step indicator */}
      <div className="flex justify-center">
        <StepIndicator currentStep={currentStep} />
      </div>

      {/* Step 1: Job Configuration */}
      <section className="rounded-lg border border-border-default bg-bg-secondary shadow-card p-6 space-y-4">
        <h2 className="text-base font-semibold text-text-primary">
          Step 1: Provide Pipeline Input
        </h2>
        <p className="text-xs text-text-muted">
          Paste ARNs (one per line for multiple), code, JSON, or any pipeline description.
          The system auto-detects what you provide.
        </p>

        {/* Input area */}
        <div>
          <textarea
            value={jobPath}
            onChange={(e) => setJobPath(e.target.value)}
            rows={7}
            placeholder={`Paste one or more inputs here:\n\n• Step Function ARN: arn:aws:states:us-east-1:...\n• MWAA ARN: arn:aws:airflow:us-east-1:...\n• ASL JSON: {"StartAt": "...", "States": {...}}\n• Airflow DAG Python code\n• Plain text description of your pipeline\n\nMultiple ARNs? One per line.`}
            className="w-full rounded-lg border border-border-default bg-bg-input px-4 py-3 text-sm font-mono
              focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20
              placeholder:text-text-muted placeholder:font-sans resize-y"
          />
        </div>

        {/* File upload */}
        <div className="flex items-center gap-3">
          <input
            ref={fileInputRef}
            type="file"
            onChange={handleFileUpload}
            accept=".py,.json,.yaml,.yml,.tf,.txt,.sql,.csv,.asl"
            className="hidden"
            id="file-upload"
          />
          <label
            htmlFor="file-upload"
            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-medium rounded-lg
              border border-border-default bg-bg-secondary text-text-secondary
              hover:bg-bg-input hover:text-text-primary cursor-pointer transition-colors"
          >
            📎 Upload File
          </label>
          {fileName && (
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-accent-subtle text-accent-primary text-xs">
              <span>📄 {fileName}</span>
              <button
                onClick={clearFile}
                className="text-status-error hover:text-red-700 font-bold"
                aria-label="Remove file"
              >
                ✕
              </button>
            </div>
          )}
          <span className="text-xs text-text-muted">
            .py .json .yaml .sql .txt .tf
          </span>
        </div>

        {/* Auto-detect hint */}
        {jobPath.trim() && (
          <div className="flex items-center gap-2 text-xs text-text-muted">
            <span>Detected:</span>
            <span className="px-2 py-0.5 rounded-full bg-bg-input font-medium text-text-secondary">
              {detectType(jobPath.trim()) === 'step_function' && '⚡ Step Function'}
              {detectType(jobPath.trim()) === 'airflow' && '🌊 Airflow'}
              {detectType(jobPath.trim()) === 'metadata' && '📄 Metadata / Description'}
            </span>
            {jobPath.trim().split('\n').filter((l) => l.trim().startsWith('arn:aws:')).length > 1 && (
              <span className="px-2 py-0.5 rounded-full bg-accent-subtle text-accent-primary font-medium">
                {jobPath.trim().split('\n').filter((l) => l.trim().startsWith('arn:aws:')).length} ARNs detected
              </span>
            )}
          </div>
        )}

        {/* Load button */}
        <button
          onClick={handleLoadJob}
          disabled={(!jobPath.trim() && !fileContent) || isLoadingJob}
          className="w-full py-2.5 rounded-md bg-accent-primary text-white text-sm font-medium
            hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isLoadingJob ? '⏳ Analyzing...' : '📂 Load & Analyze'}
        </button>

        {/* Dependencies */}
        <DependencyForm />
      </section>

      {/* Step 2: Test Cases + Step 3: Run */}
      {currentStep >= 2 && (
        <section className="rounded-lg border border-border-default bg-bg-secondary shadow-card p-6 space-y-4 animate-slide-up">
          <h2 className="text-base font-semibold text-text-primary">
            Step 2: Generate & Review Test Cases
          </h2>

          {testCases.length === 0 && (
            <button
              onClick={() => handleGenerateTests(false)}
              disabled={isGeneratingTests}
              className="w-full py-2.5 rounded-md bg-accent-teal text-white text-sm font-medium
                hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isGeneratingTests ? '⏳ Generating Test Cases...' : '🧪 Display Test Cases'}
            </button>
          )}

          {testCases.length > 0 && (
            <button
              onClick={() => handleGenerateTests(true)}
              disabled={isGeneratingTests}
              className="text-xs px-3 py-1.5 rounded-md border border-border-default text-text-secondary
                hover:bg-bg-input hover:text-text-primary transition-colors"
            >
              {isGeneratingTests ? '⏳ Regenerating...' : '🔄 Force Regenerate'}
            </button>
          )}

          <TestCaseList />

          {/* Run Tests button */}
          {testCases.length > 0 && (
            <div className="pt-4 border-t border-border-default space-y-2 animate-slide-up">
              <h3 className="text-sm font-semibold text-text-primary">
                Step 3: Execute Tests
              </h3>
              <p className="text-xs text-text-muted">
                Run {selectedTestIds.size} selected test scripts against your warehouse via Athena.
              </p>
              <button
                onClick={handleRunTests}
                disabled={isRunningTests}
                className="w-full py-3 rounded-md bg-status-success text-white text-sm font-bold
                  hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {isRunningTests ? '⏳ Running Tests...' : '▶️ Run Tests'}
              </button>
            </div>
          )}
        </section>
      )}
    </div>
  )
}
