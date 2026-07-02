import { useEffect, useRef } from 'react'
import { useAppStore } from '@/store/appStore'
import { useSessionStore } from '@/store/sessionStore'
import Sidebar from '@/components/Sidebar'
import LogPanel from '@/components/LogPanel'
import RunTests from '@/pages/RunTests'
import QueryValidator from '@/pages/QueryValidator'
import TestResultsPage from '@/pages/TestResultsPage'

export default function App() {
  const activeTab = useAppStore((s) => s.activeTab)
  const isLoadingJob = useAppStore((s) => s.isLoadingJob)
  const isGeneratingTests = useAppStore((s) => s.isGeneratingTests)
  const isRunningTests = useAppStore((s) => s.isRunningTests)
  const isQuerying = useAppStore((s) => s.isQuerying)

  const isProcessing = isLoadingJob || isGeneratingTests || isRunningTests || isQuerying

  // Loading cursor
  useEffect(() => {
    document.body.classList.toggle('cursor-loading', isProcessing)
    return () => { document.body.classList.remove('cursor-loading') }
  }, [isProcessing])

  // Restore last session on app boot
  const restored = useRef(false)
  useEffect(() => {
    if (!restored.current) {
      restored.current = true
      useSessionStore.getState().restoreLastSession()
    }
  }, [])

  // Auto-save active session on every meaningful state change
  const currentStep = useAppStore((s) => s.currentStep)
  const jobConfig = useAppStore((s) => s.jobConfig)
  const dependencies = useAppStore((s) => s.dependencies)
  const testCases = useAppStore((s) => s.testCases)
  const selectedTestIds = useAppStore((s) => s.selectedTestIds)
  const executionHistory = useAppStore((s) => s.executionHistory)
  const activeSessionId = useSessionStore((s) => s.activeSessionId)
  const saveCurrentSession = useSessionStore((s) => s.saveCurrentSession)

  useEffect(() => {
    if (!activeSessionId) return
    const timer = setTimeout(() => {
      saveCurrentSession()
    }, 300)
    return () => clearTimeout(timer)
  }, [currentStep, jobConfig, dependencies, testCases, selectedTestIds, executionHistory, activeSessionId, saveCurrentSession])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-bg-primary">
      {/* Left Sidebar */}
      <Sidebar />

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header bar */}
        <header className="flex items-center justify-between px-6 py-3 bg-bg-secondary border-b border-border-default">
          <h2 className="text-base font-semibold text-text-primary">
            {activeTab === 'run-tests' && 'Test Suite'}
            {activeTab === 'query-validator' && '🔍 Query Validator'}
            {activeTab === 'results' && '📊 Test Results'}
          </h2>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {activeTab === 'run-tests' && <RunTests />}
          {activeTab === 'query-validator' && <QueryValidator />}
          {activeTab === 'results' && <TestResultsPage />}
        </main>

        {/* Log Panel */}
        <LogPanel />
      </div>
    </div>
  )
}
