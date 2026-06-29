import { Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import Requirements from './pages/Requirements'
import TestCases from './pages/TestCases'
import TestResults from './pages/TestResults'
import CoverageReport from './pages/CoverageReport'
import AgentActivity from './pages/AgentActivity'
import RunPipeline from './pages/RunPipeline'

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-900">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/run-pipeline" element={<RunPipeline />} />
          <Route path="/requirements" element={<Requirements />} />
          <Route path="/test-cases" element={<TestCases />} />
          <Route path="/test-results" element={<TestResults />} />
          <Route path="/coverage" element={<CoverageReport />} />
          <Route path="/agent-activity" element={<AgentActivity />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
