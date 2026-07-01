import { useAppStore } from '@/store/appStore'
import Sidebar from '@/components/Sidebar'
import LogPanel from '@/components/LogPanel'
import RunTests from '@/pages/RunTests'
import QueryValidator from '@/pages/QueryValidator'
import TestResultsPage from '@/pages/TestResultsPage'

export default function App() {
  const activeTab = useAppStore((s) => s.activeTab)

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
