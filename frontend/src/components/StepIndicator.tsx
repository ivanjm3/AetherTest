import type { RunTestStep } from '@/types'

interface Props {
  currentStep: RunTestStep
}

const steps = [
  { num: 1 as const, label: 'Job Config' },
  { num: 2 as const, label: 'Test Cases' },
  { num: 3 as const, label: 'Execute' },
]

export default function StepIndicator({ currentStep }: Props) {
  return (
    <div className="flex items-center gap-2" role="progressbar" aria-valuenow={currentStep} aria-valuemin={1} aria-valuemax={3}>
      {steps.map((step, i) => (
        <div key={step.num} className="flex items-center gap-2">
          <div
            className={`
              flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold transition-colors
              ${currentStep >= step.num
                ? 'bg-accent-primary text-white'
                : 'bg-bg-input text-text-muted border border-border-default'
              }
            `}
          >
            {currentStep > step.num ? '✓' : step.num}
          </div>
          <span
            className={`text-sm font-medium ${
              currentStep >= step.num ? 'text-text-primary' : 'text-text-muted'
            }`}
          >
            {step.label}
          </span>
          {i < steps.length - 1 && (
            <div
              className={`w-8 h-0.5 mx-1 ${
                currentStep > step.num ? 'bg-accent-primary' : 'bg-border-default'
              }`}
            />
          )}
        </div>
      ))}
    </div>
  )
}
