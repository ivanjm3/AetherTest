import { useState } from 'react'
import { useAppStore } from '@/store/appStore'
import type { TestCase } from '@/types'

const categoryColors: Record<string, string> = {
  row_count: 'bg-blue-50 text-blue-700 border-blue-200',
  schema: 'bg-purple-50 text-purple-700 border-purple-200',
  null_check: 'bg-orange-50 text-orange-700 border-orange-200',
  transform: 'bg-teal-50 text-teal-700 border-teal-200',
  referential_integrity: 'bg-pink-50 text-pink-700 border-pink-200',
  freshness: 'bg-green-50 text-green-700 border-green-200',
  custom: 'bg-gray-50 text-gray-700 border-gray-200',
}

const priorityDots: Record<string, string> = {
  high: 'bg-status-error',
  medium: 'bg-status-warning',
  low: 'bg-text-muted',
}

export default function TestCaseList() {
  const testCases = useAppStore((s) => s.testCases)
  const setTestCases = useAppStore((s) => s.setTestCases)
  const selected = useAppStore((s) => s.selectedTestIds)
  const setSelectedTestIds = useAppStore((s) => s.setSelectedTestIds)
  const toggleTestId = useAppStore((s) => s.toggleTestId)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [editDraft, setEditDraft] = useState<Partial<TestCase>>({})
  const [showAddForm, setShowAddForm] = useState(false)

  if (testCases.length === 0) return null

  const selectedCount = selected.size
  const allSelected = selectedCount === testCases.length

  function selectAll() {
    setSelectedTestIds(new Set(testCases.map((t) => t.id)))
  }

  function deselectAll() {
    setSelectedTestIds(new Set())
  }

  function deleteCase(id: string) {
    setTestCases(testCases.filter((tc) => tc.id !== id))
  }

  function startEdit(tc: TestCase) {
    setEditingId(tc.id)
    setEditDraft({ ...tc })
  }

  function saveEdit() {
    if (!editingId || !editDraft) return
    setTestCases(testCases.map((tc) => tc.id === editingId ? { ...tc, ...editDraft } as TestCase : tc))
    setEditingId(null)
    setEditDraft({})
  }

  function cancelEdit() {
    setEditingId(null)
    setEditDraft({})
  }

  function addTestCase() {
    const newTc: TestCase = {
      id: `TC-${crypto.randomUUID().slice(0, 6).toUpperCase()}`,
      name: editDraft.name || 'New Test Case',
      category: (editDraft.category as TestCase['category']) || 'custom',
      description: editDraft.description || '',
      user_story: editDraft.user_story || '',
      sql: editDraft.sql || 'SELECT 1;',
      expected: editDraft.expected || 'Expected result',
      priority: (editDraft.priority as TestCase['priority']) || 'medium',
    }
    setTestCases([...testCases, newTc])
    setShowAddForm(false)
    setEditDraft({})
  }

  function downloadScripts() {
    const cases = testCases.filter((tc) => selected.has(tc.id))
    const content = cases
      .map((tc) => `-- Test: ${tc.name}\n-- Story: ${tc.user_story || tc.description}\n-- Expected: ${tc.expected}\n${tc.sql}\n`)
      .join('\n---\n\n')
    const blob = new Blob([content], { type: 'text/sql' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'test_scripts.sql'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="space-y-3 animate-slide-up">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-text-primary">Test Cases</h3>
          <span className="text-xs text-text-muted">{selectedCount}/{testCases.length} selected</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => allSelected ? deselectAll() : selectAll()}
            className="text-xs px-2 py-1 rounded-md border border-border-default hover:bg-bg-input text-text-secondary transition-colors"
          >
            {allSelected ? 'Deselect All' : 'Select All'}
          </button>
          <button
            onClick={() => { setShowAddForm(true); setEditDraft({}) }}
            className="text-xs px-2 py-1 rounded-md bg-accent-subtle text-accent-primary hover:bg-accent-primary hover:text-white transition-colors font-medium"
          >
            + Add Test
          </button>
          <button
            onClick={downloadScripts}
            disabled={selectedCount === 0}
            className="text-xs px-2 py-1 rounded-md bg-accent-subtle text-accent-primary hover:bg-accent-primary hover:text-white disabled:opacity-40 transition-colors font-medium"
          >
            ⬇️ Download ({selectedCount})
          </button>
        </div>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="rounded-lg border-2 border-dashed border-accent-primary/40 bg-accent-subtle/30 p-4 space-y-3 animate-slide-up">
          <h4 className="text-xs font-semibold text-accent-primary uppercase tracking-wide">New Test Case</h4>
          <input placeholder="Test name" value={editDraft.name || ''} onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })}
            className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20" />
          <textarea placeholder="User story (As a... I want... So that...)" value={editDraft.user_story || ''} onChange={(e) => setEditDraft({ ...editDraft, user_story: e.target.value })} rows={2}
            className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20 resize-y" />
          <textarea placeholder="SQL query" value={editDraft.sql || ''} onChange={(e) => setEditDraft({ ...editDraft, sql: e.target.value })} rows={3}
            className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm font-mono focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20 resize-y" />
          <input placeholder="Expected result" value={editDraft.expected || ''} onChange={(e) => setEditDraft({ ...editDraft, expected: e.target.value })}
            className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20" />
          <div className="flex gap-2">
            <button onClick={addTestCase} className="px-3 py-1.5 text-xs font-medium rounded-md bg-accent-primary text-white hover:bg-accent-hover transition-colors">Add</button>
            <button onClick={() => setShowAddForm(false)} className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-default text-text-secondary hover:bg-bg-input transition-colors">Cancel</button>
          </div>
        </div>
      )}

      {/* Test case list */}
      <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
        {testCases.map((tc) => (
          <div
            key={tc.id}
            className={`rounded-lg border transition-all duration-150 ${
              selected.has(tc.id) ? 'border-border-default bg-bg-secondary shadow-card' : 'border-border-subtle bg-bg-input/30 opacity-50'
            }`}
          >
            {editingId === tc.id ? (
              <div className="p-4 space-y-2 animate-fade-in">
                <input value={editDraft.name || ''} onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })}
                  className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm font-medium focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20" />
                <textarea value={editDraft.user_story || ''} onChange={(e) => setEditDraft({ ...editDraft, user_story: e.target.value })} rows={2} placeholder="User story"
                  className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20 resize-y" />
                <textarea value={editDraft.sql || ''} onChange={(e) => setEditDraft({ ...editDraft, sql: e.target.value })} rows={4}
                  className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm font-mono focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20 resize-y" />
                <input value={editDraft.expected || ''} onChange={(e) => setEditDraft({ ...editDraft, expected: e.target.value })} placeholder="Expected result"
                  className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20" />
                <div className="flex gap-2">
                  <button onClick={saveEdit} className="px-3 py-1.5 text-xs font-medium rounded-md bg-status-success text-white hover:opacity-90 transition-colors">Save</button>
                  <button onClick={cancelEdit} className="px-3 py-1.5 text-xs font-medium rounded-md border border-border-default text-text-secondary hover:bg-bg-input transition-colors">Cancel</button>
                </div>
              </div>
            ) : (
              <details className="group">
                <summary className="flex items-center gap-3 px-4 py-3 cursor-pointer list-none">
                  {/* Checkbox */}
                  <label className="relative flex items-center cursor-pointer shrink-0" onClick={(e) => e.stopPropagation()}>
                    <input type="checkbox" checked={selected.has(tc.id)} onChange={() => toggleTestId(tc.id)} className="peer sr-only" />
                    <div className="w-[18px] h-[18px] rounded border-2 border-border-default bg-bg-secondary peer-checked:bg-accent-primary peer-checked:border-accent-primary flex items-center justify-center transition-colors">
                      {selected.has(tc.id) && (
                        <svg className="w-2.5 h-2.5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                        </svg>
                      )}
                    </div>
                  </label>

                  <div className={`w-2 h-2 rounded-full shrink-0 ${priorityDots[tc.priority]}`} />

                  {/* User story / description */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text-primary">{tc.name}</p>
                    <p className="text-xs text-text-secondary mt-0.5">
                      {tc.user_story || tc.description}
                    </p>
                  </div>

                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium border shrink-0 ${categoryColors[tc.category] ?? categoryColors['custom']}`}>
                    {tc.category.replace(/_/g, ' ')}
                  </span>

                  {/* Actions */}
                  <div className="flex items-center gap-1 shrink-0" onClick={(e) => e.stopPropagation()}>
                    <button onClick={() => startEdit(tc)} className="p-1.5 rounded-md text-text-muted hover:text-accent-primary hover:bg-accent-subtle transition-colors" title="Edit">✏️</button>
                    <button onClick={() => deleteCase(tc.id)} className="p-1.5 rounded-md text-text-muted hover:text-status-error hover:bg-red-50 transition-colors" title="Delete">🗑️</button>
                  </div>

                  <span className="text-text-muted text-xs group-open:rotate-90 transition-transform">▶</span>
                </summary>

                {/* SQL dropdown */}
                <div className="px-4 pb-3 space-y-2 border-t border-border-subtle animate-fade-in">
                  <div className="pt-2">
                    <p className="text-xs font-medium text-text-secondary mb-1">SQL Query:</p>
                    <div className="rounded-md bg-[#0f172a] p-3 overflow-x-auto">
                      <code className="text-xs text-green-400 font-mono whitespace-pre-wrap">{tc.sql}</code>
                    </div>
                  </div>
                  <p className="text-xs text-text-muted">
                    <span className="font-medium">Expected:</span> {tc.expected}
                  </p>
                </div>
              </details>
            )}
          </div>
        ))}
      </div>

      {selectedCount < testCases.length && (
        <p className="text-xs text-status-warning flex items-center gap-1">
          ⚠️ Only {selectedCount} of {testCases.length} tests will be executed.
        </p>
      )}
    </div>
  )
}
