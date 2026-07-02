import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Session } from '@/types'
import { useAppStore } from './appStore'

interface SessionState {
  sessions: Session[]
  activeSessionId: string | null

  /** Auto-creates a session if none active. Called on first meaningful action. */
  ensureSession: () => string
  createSession: (name?: string) => string
  renameSession: (id: string, name: string) => void
  deleteSession: (id: string) => void
  switchSession: (id: string) => void
  saveCurrentSession: () => void
  /** Restores last active session on app boot */
  restoreLastSession: () => void
}

function generateId() {
  return crypto.randomUUID()
}

function generateSessionName(input?: string): string {
  if (input) {
    // Derive name from ARN or input content
    const lines = input.split('\n').filter((l) => l.trim())
    const firstLine = lines[0] || ''
    if (firstLine.startsWith('arn:aws:states:')) {
      const parts = firstLine.split(':stateMachine:')
      if (parts[1]) return parts[1].slice(0, 40)
    }
    if (firstLine.startsWith('arn:aws:airflow:')) {
      const parts = firstLine.split(':environment/')
      if (parts[1]) return parts[1].slice(0, 40)
    }
    if (firstLine.startsWith('arn:aws:')) {
      return firstLine.slice(0, 50)
    }
    // For other inputs, use truncated first line
    return firstLine.slice(0, 40) || defaultTimeName()
  }
  return defaultTimeName()
}

function defaultTimeName(): string {
  return `Session ${new Date().toLocaleDateString()} ${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

/** Snapshot current appStore state into a serializable session state object */
function snapshotAppState(): Session['state'] {
  const s = useAppStore.getState()
  return {
    currentStep: s.currentStep,
    jobConfig: s.jobConfig,
    dependencies: s.dependencies,
    testCases: s.testCases,
    selectedTestIds: Array.from(s.selectedTestIds),
    executionHistory: s.executionHistory,
  }
}

/** Restore appStore state from a session state object */
function restoreAppState(state: Session['state']) {
  const store = useAppStore.getState()
  store.setCurrentStep(state.currentStep)
  store.setJobConfig(state.jobConfig)
  store.setDependencies(state.dependencies)
  useAppStore.setState({
    testCases: state.testCases,
    selectedTestIds: new Set(state.selectedTestIds),
    executionHistory: state.executionHistory,
  })
}

export const useSessionStore = create<SessionState>()(
  persist(
    (set, get) => ({
      sessions: [],
      activeSessionId: null,

      ensureSession: () => {
        const { activeSessionId } = get()
        if (activeSessionId) return activeSessionId

        // Auto-create session from current app state input
        const appState = useAppStore.getState()
        const input = appState.jobConfig?.path
        const name = generateSessionName(input || undefined)
        return get().createSession(name)
      },

      createSession: (name?: string) => {
        const { activeSessionId } = get()

        // Save current session before creating new one
        if (activeSessionId) {
          get().saveCurrentSession()
        }

        const id = generateId()
        const now = new Date().toISOString()
        const session: Session = {
          id,
          name: name || defaultTimeName(),
          createdAt: now,
          updatedAt: now,
          state: {
            currentStep: 1,
            jobConfig: null,
            dependencies: [],
            testCases: [],
            selectedTestIds: [],
            executionHistory: [],
          },
        }

        set((s) => ({
          sessions: [session, ...s.sessions],
          activeSessionId: id,
        }))

        // Reset app state for new session
        useAppStore.getState().reset()

        return id
      },

      renameSession: (id, name) => {
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === id ? { ...sess, name, updatedAt: new Date().toISOString() } : sess
          ),
        }))
      },

      deleteSession: (id) => {
        const { activeSessionId, sessions } = get()
        const filtered = sessions.filter((s) => s.id !== id)

        if (activeSessionId === id) {
          if (filtered.length > 0) {
            const next = filtered[0]!
            set({ sessions: filtered, activeSessionId: next.id })
            restoreAppState(next.state)
          } else {
            set({ sessions: [], activeSessionId: null })
            useAppStore.getState().reset()
          }
        } else {
          set({ sessions: filtered })
        }
      },

      switchSession: (id) => {
        const { activeSessionId, sessions } = get()
        if (activeSessionId === id) return

        // Auto-save current session
        if (activeSessionId) {
          get().saveCurrentSession()
        }

        // Load target session
        const target = sessions.find((s) => s.id === id)
        if (target) {
          set({ activeSessionId: id })
          restoreAppState(target.state)
        }
      },

      saveCurrentSession: () => {
        const { activeSessionId } = get()
        if (!activeSessionId) return

        const snapshot = snapshotAppState()
        set((s) => ({
          sessions: s.sessions.map((sess) =>
            sess.id === activeSessionId
              ? { ...sess, state: snapshot, updatedAt: new Date().toISOString() }
              : sess
          ),
        }))
      },

      restoreLastSession: () => {
        const { activeSessionId, sessions } = get()
        if (activeSessionId) {
          const target = sessions.find((s) => s.id === activeSessionId)
          if (target) {
            restoreAppState(target.state)
          }
        }
      },
    }),
    {
      name: 'aethertest-sessions',
    }
  )
)
