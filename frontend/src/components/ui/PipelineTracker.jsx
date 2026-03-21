import { Check, Loader2 } from 'lucide-react'
import { PIPELINE_STEPS } from '../../constants'

export default function PipelineTracker({ planSteps, stepStatuses = {} }) {
  if (!planSteps || planSteps.length === 0) return null

  // Map plan step names to pipeline step keys
  const stepMap = {
    document_intelligence: 'doc',
    regulatory_retrieval:  'reg',
    risk_scoring:          'risk',
    report_summarisation:  'report',
  }

  const activeSteps = PIPELINE_STEPS.filter(s =>
    planSteps.some(ps => stepMap[ps] === s.key)
  )

  if (activeSteps.length === 0) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap', marginTop: 4 }}>
      {activeSteps.map((step, i) => {
        const status = stepStatuses[step.key] || 'pending'
        const isLast = i === activeSteps.length - 1

        return (
          <div key={step.key} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              {status === 'done' && (
                <Check size={10} style={{ color: 'var(--success)' }} />
              )}
              {status === 'running' && (
                <Loader2 size={10} style={{ color: 'var(--gold)' }} className="animate-spin" />
              )}
              {status === 'pending' && (
                <div style={{ width: 4, height: 4, borderRadius: '50%', background: 'var(--text-muted)' }} />
              )}
              <span style={{
                fontSize: 11,
                fontFamily: 'var(--font-mono)',
                color: status === 'done' ? 'var(--text-secondary)'
                     : status === 'running' ? 'var(--gold)'
                     : 'var(--text-muted)',
                transition: 'color 0.2s',
              }}>
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div style={{ width: 12, height: 1, background: 'var(--border-bright)' }} />
            )}
          </div>
        )
      })}
    </div>
  )
}