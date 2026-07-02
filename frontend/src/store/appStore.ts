import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  ActiveTab,
  RunTestStep,
  JobConfig,
  Dependency,
  TestCase,
  ExecutionRun,
  LogEntry,
  QueryResult,
} from '@/types'

interface AppState {
  // Navigation
  activeTab: ActiveTab

  // Tab 1: Run Tests
  currentStep: RunTestStep
  jobConfig: JobConfig | null
  dependencies: Dependency[]
  testCases: TestCase[]
  selectedTestIds: Set<string>
  isLoadingJob: boolean
  isGeneratingTests: boolean
  isRunningTests: boolean

  // Tab 2: Query Validator
  lastQueryResult: QueryResult | null
  isQuerying: boolean

  // Tab 3: Results
  executionHistory: ExecutionRun[]

  // Log panel
  logs: LogEntry[]
  logPanelOpen: boolean

  // Actions
  setActiveTab: (tab: ActiveTab) => void
  setCurrentStep: (step: RunTestStep) => void
  setJobConfig: (config: JobConfig | null) => void
  setDependencies: (deps: Dependency[]) => void
  updateDependency: (id: string, value: string) => void
  toggleDependency: (id: string) => void
  selectAllDependencies: (selected: boolean) => void
  setTestCases: (cases: TestCase[]) => void
  setSelectedTestIds: (ids: Set<string>) => void
  toggleTestId: (id: string) => void
  setIsLoadingJob: (v: boolean) => void
  setIsGeneratingTests: (v: boolean) => void
  setIsRunningTests: (v: boolean) => void
  setLastQueryResult: (r: QueryResult | null) => void
  setIsQuerying: (v: boolean) => void
  addExecutionRun: (run: ExecutionRun) => void
  updateExecutionAnalysis: (runId: string, analysis: ExecutionRun['analysis']) => void
  addLog: (level: LogEntry['level'], message: string) => void
  clearLogs: () => void
  toggleLogPanel: () => void
  reset: () => void
}

const initialState = {
  activeTab: 'run-tests' as ActiveTab,
  currentStep: 1 as RunTestStep,
  jobConfig: null,
  dependencies: [],
  testCases: [],
  selectedTestIds: new Set<string>(),
  isLoadingJob: false,
  isGeneratingTests: false,
  isRunningTests: false,
  lastQueryResult: null,
  isQuerying: false,
  executionHistory: [],
  logs: [],
  logPanelOpen: true,
}

export const useAppStore = create<AppState>()(
  persist(
    (set) => ({
      ...initialState,

      setActiveTab: (tab) => set({ activeTab: tab }),
      setCurrentStep: (step) => set({ currentStep: step }),
      setJobConfig: (config) => set({ jobConfig: config }),
      setDependencies: (deps) => set({ dependencies: deps }),
      updateDependency: (id, value) =>
        set((s) => ({
          dependencies: s.dependencies.map((d) =>
            d.id === id ? { ...d, value } : d
          ),
        })),
      toggleDependency: (id) =>
        set((s) => ({
          dependencies: s.dependencies.map((d) =>
            d.id === id ? { ...d, selected: !d.selected } : d
          ),
        })),
      selectAllDependencies: (selected) =>
        set((s) => ({
          dependencies: s.dependencies.map((d) => ({ ...d, selected })),
        })),
      setTestCases: (cases) => set({ testCases: cases, selectedTestIds: new Set(cases.map((c) => c.id)) }),
      setSelectedTestIds: (ids) => set({ selectedTestIds: ids }),
      toggleTestId: (id) => set((s) => {
        const next = new Set(s.selectedTestIds)
        if (next.has(id)) next.delete(id)
        else next.add(id)
        return { selectedTestIds: next }
      }),
      setIsLoadingJob: (v) => set({ isLoadingJob: v }),
      setIsGeneratingTests: (v) => set({ isGeneratingTests: v }),
      setIsRunningTests: (v) => set({ isRunningTests: v }),
      setLastQueryResult: (r) => set({ lastQueryResult: r }),
      setIsQuerying: (v) => set({ isQuerying: v }),
      addExecutionRun: (run) =>
        set((s) => ({ executionHistory: [run, ...s.executionHistory] })),
      updateExecutionAnalysis: (runId, analysis) =>
        set((s) => ({
          executionHistory: s.executionHistory.map((run) =>
            run.id === runId ? { ...run, analysis } : run
          ),
        })),
      addLog: (level, message) =>
        set((s) => ({
          logs: [
            ...s.logs,
            {
              id: crypto.randomUUID(),
              timestamp: new Date().toISOString(),
              level,
              message,
            },
          ],
        })),
      clearLogs: () => set({ logs: [] }),
      toggleLogPanel: () => set((s) => ({ logPanelOpen: !s.logPanelOpen })),
      reset: () => set(initialState),
    }),
    {
      name: 'aethertest-dataflow',
      partialize: (state) => ({
        executionHistory: state.executionHistory,
        logPanelOpen: state.logPanelOpen,
      }),
    }
  )
)
