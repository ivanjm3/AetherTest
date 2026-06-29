import { useEffect, useState } from 'react'
import { scanTable } from '../lib/aws'

interface AgentAssignment {
  agent: string
  run_id: string
  tenant_id: string
  status: string
  task: string
  started_at: string
  completed_at?: string
  duration_ms?: number
  result_summary?: string
}

const ASSIGNMENTS_TABLE = 'aethertest-agent-assignments'

const AGENT_EMOJIS: Record<string, string> = {
  'test strategist': '🧠',
  'test author': '✍️',
  'test executor': '▶️',
  'test analyst': '🔍',
  'test maintenance': '🔧',
  'coverage & risk': '📊',
  'coverage_risk': '📊',
  'strategy_generator': '🧠',
  'test_author': '✍️',
  'test_executor': '▶️',
  'test_analyst': '🔍',
  'test_maintenance': '🔧',
}

export default function AgentActivity() {
  const [activities, setActivities] = useState<AgentAssignment[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [filterAgent, setFilterAgent] = useState<string>('all')

  useEffect(() => {
    fetchActivity()
  }, [])

  async function fetchActivity() {
    setLoading(true)
    setError(null)
    try {
      const items = await scanTable(ASSIGNMENTS_TABLE, 100)
      const mapped: AgentAssignment[] = items.map((item) => ({
        agent: (item['agent'] as string) ?? (item['agent_name'] as string) ?? 'unknown',
        run_id: (item['run_id'] as string) ?? (item['SK'] as string) ?? '',
        tenant_id: (item['tenant_id'] as string) ?? '',
        status: (item['status'] as string) ?? 'unknown',
        task: (item['task'] as string) ?? (item['task_description'] as string) ?? '',
        started_at: (item['started_at'] as string) ?? (item['timestamp'] as string) ?? '',
        completed_at: (item['completed_at'] as string) ?? undefined,
        duration_ms: (item['duration_ms'] as number) ?? undefined,
        result_summary: (item['result_summary'] as string) ?? undefined,
      }))
      // Sort by start time descending
      mapped.sort((a, b) => (b.started_at > a.started_at ? 1 : -1))
      setActivities(mapped)
    } catch (err) {
      setError(`Failed to fetch agent activity: ${err instanceof Error ? err.message : String(err)}`)
    } finally {
      setLoading(false)
    }
  }

  const uniqueAgents = [...new Set(activities.map(a => a.agent))]
  const filtered = filterAgent === 'all'
    ? activities
    : activities.filter(a => a.agent === filterAgent)

  // Group by run_id
  const groupedByRun = new Map<string, AgentAssignment[]>()
  for (const act of filtered) {
    const key = act.run_id || 'no-run'
    if (!groupedByRun.has(key)) groupedByRun.set(key, [])
    groupedByRun.get(key)!.push(act)
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">🤖 Agent Activity</h1>
      <p className="text-gray-600 dark:text-gray-400">
        Detailed log of what each agent did per run with timestamps
      </p>

      {/* Controls */}
      <div className="bg-white dark:bg-gray-800 rounded-lg p-4 shadow-sm border border-gray-200 dark:border-gray-700 flex gap-4 items-end flex-wrap">
        <div>
          <label className="block text-sm font-medium mb-1">Filter by Agent</label>
          <select
            className="rounded-md border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 px-3 py-2 text-sm"
            value={filterAgent}
            onChange={e => setFilterAgent(e.target.value)}
          >
            <option value="all">All Agents</option>
            {uniqueAgents.map(a => (
              <option key={a} value={a}>{a}</option>
            ))}
          </select>
        </div>
        <button
          onClick={fetchActivity}
          disabled={loading}
          className="px-4 py-2 text-sm rounded-md bg-blue-600 text-white font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          🔄 Refresh
        </button>
        <p className="text-sm text-gray-500 dark:text-gray-400">
          {filtered.length} activities {filterAgent !== 'all' ? `for ${filterAgent}` : 'total'}
        </p>
      </div>

      {loading && <p className="text-sm text-gray-500">Loading agent activity...</p>}
      {error && <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>}

      {/* Grouped Activity */}
      {[...groupedByRun.entries()].map(([runId, acts]) => (
        <section key={runId} className="space-y-2">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 flex items-center gap-2">
            <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 rounded text-xs font-mono">
              Run: {runId}
            </span>
            <span className="text-xs text-gray-500">{acts.length} action(s)</span>
          </h3>
          <div className="space-y-2 pl-3 border-l-2 border-gray-200 dark:border-gray-700">
            {acts.map((act, i) => (
              <ActivityRow key={`${act.agent}-${act.started_at}-${i}`} activity={act} />
            ))}
          </div>
        </section>
      ))}

      {activities.length === 0 && !loading && !error && (
        <p className="text-sm text-gray-500 dark:text-gray-400">
          No agent activity found. Activity is recorded when agents execute tasks during test cycles.
        </p>
      )}
    </div>
  )
}

function ActivityRow({ activity }: { activity: AgentAssignment }) {
  const emoji = getAgentEmoji(activity.agent)
  const statusColor = getStatusColor(activity.status)

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700 flex items-start gap-3">
      <span className="text-lg flex-shrink-0 mt-0.5">{emoji}</span>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="font-medium text-sm">{activity.agent}</span>
          <span className={`inline-block px-2 py-0.5 rounded-full text-xs font-medium ${statusColor}`}>
            {activity.status}
          </span>
        </div>
        {activity.task && (
          <p className="text-sm text-gray-600 dark:text-gray-400">{activity.task}</p>
        )}
        {activity.result_summary && (
          <p className="text-xs text-gray-500 dark:text-gray-400 italic">{activity.result_summary}</p>
        )}
        <div className="flex gap-4 text-xs text-gray-500 dark:text-gray-400">
          {activity.started_at && (
            <span>Started: {new Date(activity.started_at).toLocaleString()}</span>
          )}
          {activity.completed_at && (
            <span>Completed: {new Date(activity.completed_at).toLocaleString()}</span>
          )}
          {activity.duration_ms != null && activity.duration_ms > 0 && (
            <span>Duration: {(activity.duration_ms / 1000).toFixed(1)}s</span>
          )}
        </div>
      </div>
    </div>
  )
}

function getAgentEmoji(agent: string): string {
  const lower = agent.toLowerCase()
  for (const [key, emoji] of Object.entries(AGENT_EMOJIS)) {
    if (lower.includes(key)) return emoji
  }
  return '🤖'
}

function getStatusColor(status: string): string {
  switch (status) {
    case 'completed':
    case 'success':
      return 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
    case 'active':
    case 'running':
    case 'in_progress':
      return 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300'
    case 'failed':
    case 'error':
      return 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
    case 'idle':
      return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
    default:
      return 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
  }
}
