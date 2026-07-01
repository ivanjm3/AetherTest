import type { QueryMode, QueryResult } from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8001'

export async function executeQuery(
  input: string,
  mode: QueryMode,
  connectionId?: string
): Promise<QueryResult> {
  const res = await fetch(`${API_BASE}/api/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ input, mode, connection_id: connectionId }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: `HTTP ${res.status}` }))
    throw new Error(err.error || `Query failed: ${res.status}`)
  }
  return res.json()
}
