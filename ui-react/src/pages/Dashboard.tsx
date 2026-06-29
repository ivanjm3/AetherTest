import { useEffect, useState } from 'react'
import { scanTable } from '../lib/aws'

interface AgentStatus {
  name: string
  emoji: string
  description: string
  status: string
}

const AGENTS: AgentStatus[] = [
  { name: 'Test Strategist', emoji: '🧠', description: 'AUT analysis, risk scoring, strategy generation', status: 'idle' },
  { name: 'Test Author', emoji: '✍️', description: 'Converts requirements to BDD test cases', status: 'idle' },
  { name: 'Test Executor', emoji: '▶️', description: 'Runs tests with self-healing', status: 'idle' },
  { name: 'Test Analyst', emoji: '🔍', description: 'Root cause analysis and failure classification', status: 'idle' },
  { name: 'Test Maintenance', emoji: '🔧', description: 'Updates tests when AUT changes', status: 'idle' },
  { name: 'Coverage & Risk', emoji: '📊', description: 'Coverage mapping and deployment verdicts', status: 'idle' },
]

const ASSIGNMENTS_TABLE = 'aethertest-agent-assignments'

export default function Dashboard() {
  const [agents, setAgents] = useState<AgentStatus[]>(AGENTS)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    async function fetchAgentStatuses() {
      setLoading(true)
      try {
        const items = await scanTable(ASSIGNMENTS_TABLE, 50)
        // Map agent assignments to agent list
        const statusMap = new Map<string, string>()
        for (const item of items) {
          const agent = item['agent'] as string | undefined
          const status = item['status'] as string | undefined
          if (agent && status) {
            statusMap.set(agent.toLowerCase(), status)
          }
        }
        setAgents(AGENTS.map(a => ({
          ...a,
          status: statusMap.get(a.name.toLowerCase()) ?? 'idle',
        })))
      } catch (err) {
        console.error('Failed to fetch agent statuses:', err)
      } finally {
        setLoading(false)
      }
    }
    fetchAgentStatuses()
  }, [])

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">🏠 AetherTest Dashboard</h1>
      <p className="text-gray-600 dark:text-gray-400">
        Welcome to the AetherTest Multi-Agent AI Testing Platform
      </p>

      {/* Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard label="Total Agents" value="6" />
        <MetricCard label="AWS Region" value="us-east-1" />
        <MetricCard label="Bedrock Model" value="Claude Sonnet 4" />
      </div>

      {/* Platform Overview */}
      <section className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm border border-gray-200 dark:border-gray-700">
        <h2 className="text-lg font-semibold mb-3">Platform Overview</h2>
        <p className="text-gray-600 dark:text-gray-400 mb-3">
          AetherTest is an AWS-native multi-agent AI testing solution that uses Claude Sonnet 4 to:
        </p>
        <ul className="list-disc list-inside space-y-1 text-gray-600 dark:text-gray-400 text-sm">
          <li><strong>Analyze</strong> application structure and compute risk scores</li>
          <li><strong>Generate</strong> test strategies and test cases from requirements</li>
          <li><strong>Execute</strong> tests with self-healing capabilities</li>
          <li><strong>Analyze</strong> failures with root cause analysis</li>
          <li><strong>Maintain</strong> tests when the application changes</li>
          <li><strong>Report</strong> coverage and provide deployment verdicts</li>
        </ul>
      </section>

      {/* Agent Grid */}
      <section>
        <h2 className="text-lg font-semibold mb-3">6 Intelligent Agents</h2>
        {loading && <p className="text-sm text-gray-500">Loading agent statuses...</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <div
              key={agent.name}
              className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-2xl">{agent.emoji}</span>
                <h3 className="font-medium">{agent.name}</h3>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400">{agent.description}</p>
              <div className="mt-3">
                <StatusBadge status={agent.status} />
              </div>
            </div>
          ))}
        </div>
      </section>
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

function StatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    idle: 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300',
    active: 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
    running: 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300',
    error: 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300',
  }
  const cls = colors[status] ?? colors['idle']
  return (
    <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status}
    </span>
  )
}
