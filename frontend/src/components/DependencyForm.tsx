import { useAppStore } from '@/store/appStore'

const typeIcons = {
  source: '📥',
  target: '📤',
  connection: '🔗',
}

const typeBadgeColors = {
  source: 'bg-blue-50 text-blue-700 border-blue-200',
  target: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  connection: 'bg-violet-50 text-violet-700 border-violet-200',
}

export default function DependencyForm() {
  const dependencies = useAppStore((s) => s.dependencies)
  const updateDependency = useAppStore((s) => s.updateDependency)
  const toggleDependency = useAppStore((s) => s.toggleDependency)
  const selectAllDependencies = useAppStore((s) => s.selectAllDependencies)

  if (dependencies.length === 0) return null

  const selectedCount = dependencies.filter((d) => d.selected).length
  const allSelected = selectedCount === dependencies.length

  return (
    <div className="space-y-3 animate-slide-up">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">
            Discovered Dependencies
          </h3>
          <p className="text-xs text-text-muted mt-0.5">
            Select which sources/targets/connections to include in test generation.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-text-muted">
            {selectedCount}/{dependencies.length} selected
          </span>
          <button
            onClick={() => selectAllDependencies(!allSelected)}
            className="text-xs px-2 py-1 rounded-md border border-border-default
              hover:bg-bg-input text-text-secondary hover:text-text-primary transition-colors"
          >
            {allSelected ? 'Deselect All' : 'Select All'}
          </button>
        </div>
      </div>

      <div className="space-y-2">
        {dependencies.map((dep) => (
          <div
            key={dep.id}
            className={`
              flex items-center gap-3 p-3 rounded-lg border transition-all duration-150
              ${dep.selected
                ? 'border-accent-primary/30 bg-bg-secondary shadow-card'
                : 'border-border-default bg-bg-input/50 opacity-60'
              }
            `}
          >
            {/* Checkbox */}
            <label className="relative flex items-center cursor-pointer shrink-0">
              <input
                type="checkbox"
                checked={dep.selected}
                onChange={() => toggleDependency(dep.id)}
                className="peer sr-only"
              />
              <div className="w-5 h-5 rounded-md border-2 border-border-default bg-bg-secondary
                peer-checked:bg-accent-primary peer-checked:border-accent-primary
                flex items-center justify-center transition-colors">
                {dep.selected && (
                  <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                )}
              </div>
            </label>

            {/* Icon */}
            <span className="text-lg shrink-0">{typeIcons[dep.type]}</span>

            {/* Content */}
            <div className="flex-1 min-w-0">
              <label className="block text-xs font-medium text-text-secondary mb-1">
                {dep.label}
              </label>
              <input
                type="text"
                value={dep.value}
                onChange={(e) => updateDependency(dep.id, e.target.value)}
                disabled={!dep.editable || !dep.selected}
                className="w-full rounded-md border border-border-default bg-bg-secondary px-3 py-1.5 text-sm font-mono
                  focus:border-accent-primary focus:ring-1 focus:ring-accent-primary/20
                  disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              />
            </div>

            {/* Type badge */}
            <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${typeBadgeColors[dep.type]}`}>
              {dep.type}
            </span>

            {/* Source ARN tag (when multiple inputs) */}
            {dep.sourceArn && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-bg-input text-text-muted border border-border-subtle truncate max-w-[140px]" title={dep.sourceArn}>
                {dep.sourceArn.includes(':stateMachine:')
                  ? dep.sourceArn.split(':stateMachine:')[1]
                  : dep.sourceArn.includes(':environment/')
                    ? dep.sourceArn.split(':environment/')[1]
                    : dep.sourceArn.slice(0, 20)}
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
