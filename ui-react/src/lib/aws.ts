/**
 * Centralised AWS wrapper.
 * All AWS calls go through the local API server (api-server.py) to avoid
 * browser CORS issues with direct AWS SDK calls.
 *
 * In production (deployed to ECS), swap this to call AWS SDK directly or
 * route through API Gateway.
 */

const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

// ── DynamoDB helpers ─────────────────────────────────────────────────────────

export async function scanTable(
  tableName: string,
  limit = 50,
): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams({ table: tableName, limit: String(limit) })
  const res = await fetch(`${API_BASE}/api/dynamodb/scan?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as Record<string, string>).error || `Scan failed: ${res.status}`)
  }
  const data = await res.json() as { items: Record<string, unknown>[] }
  return data.items
}

export async function queryTable(
  tableName: string,
  pk: string,
  limit = 20,
): Promise<Record<string, unknown>[]> {
  const params = new URLSearchParams({ table: tableName, pk, limit: String(limit) })
  const res = await fetch(`${API_BASE}/api/dynamodb/query?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as Record<string, string>).error || `Query failed: ${res.status}`)
  }
  const data = await res.json() as { items: Record<string, unknown>[] }
  return data.items
}

// ── S3 helpers ───────────────────────────────────────────────────────────────

interface S3Object {
  Key: string
  Size: number
  LastModified: string
}

export async function listS3Objects(prefix: string, maxKeys = 100): Promise<S3Object[]> {
  const params = new URLSearchParams({ prefix, maxKeys: String(maxKeys) })
  const res = await fetch(`${API_BASE}/api/s3/list?${params}`)
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as Record<string, string>).error || `S3 list failed: ${res.status}`)
  }
  const data = await res.json() as { contents: S3Object[] }
  return data.contents
}

export async function getS3Object<T = unknown>(key: string): Promise<T | null> {
  const params = new URLSearchParams({ key })
  const res = await fetch(`${API_BASE}/api/s3/get?${params}`)
  if (!res.ok) {
    if (res.status === 404) return null
    const err = await res.json().catch(() => ({}))
    throw new Error((err as Record<string, string>).error || `S3 get failed: ${res.status}`)
  }
  return (await res.json()) as T
}

// ── Lambda helpers (kept for future production use) ──────────────────────────

export async function invokeLambda<T = unknown>(
  functionName: string,
  payload: Record<string, unknown>,
): Promise<T> {
  // In local dev, this isn't used (Requirements page calls /api/test-author directly).
  // In production, this would use AWS SDK Lambda client.
  const res = await fetch(`${API_BASE}/api/test-author`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...payload, _functionName: functionName }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error((err as Record<string, string>).error || `Lambda invoke failed: ${res.status}`)
  }
  return (await res.json()) as T
}
