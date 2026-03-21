import { useMemo } from 'react'
import { Shield, BarChart3 } from 'lucide-react'
import IntentBadge    from '../ui/IntentBadge'
import PipelineTracker from '../ui/PipelineTracker'
import VerdictBadge   from '../ui/VerdictBadge'
import RiskBadge      from '../ui/RiskBadge'
import ScoreBar       from '../ui/ScoreBar'
import Collapsible    from '../ui/Collapsible'
import { formatTime } from '../../lib/utils'
import { renderMarkdownToHtml } from '../../lib/markdown'

function ThinkingDots() {
  return (
    <div style={{ display: 'flex', gap: 5, padding: '4px 0' }}>
      {[0, 1, 2].map(i => (
        <div key={i} style={{
          width: 6, height: 6, borderRadius: '50%',
          background: 'var(--text-muted)',
          animation: `shimmer 1.4s ease ${i * 0.2}s infinite`,
        }} />
      ))}
    </div>
  )
}

export default function AssistantMessage({ message }) {
  const {
    content, isStreaming, intent, plan, planSteps,
    stepStatuses, riskScore, verdict, timestamp,
  } = message
  const renderedContent = useMemo(() => renderMarkdownToHtml(content), [content])

  const showThinking = isStreaming && !content && !plan

  return (
    <div style={{ display: 'flex', gap: 10 }} className="animate-fade-up">

      {/* Avatar */}
      <div style={{
        width: 30, height: 30, borderRadius: 8, flexShrink: 0,
        background: 'var(--gold-dim)', border: '1px solid var(--gold-glow)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', marginTop: 2,
      }}>
        <Shield size={13} style={{ color: 'var(--gold)' }} />
      </div>

      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Intent + Pipeline */}
        {(intent || planSteps) && (
          <div style={{ marginBottom: 6 }}>
            {intent && <IntentBadge intent={intent} />}
            {planSteps && (
              <PipelineTracker planSteps={planSteps} stepStatuses={stepStatuses} />
            )}
          </div>
        )}

        {/* Bubble */}
        <div style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: '2px 10px 10px 10px', padding: '12px 16px',
        }}>
          {/* Reasoning from plan */}
          {plan?.reasoning && (
            <p style={{
              fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)',
              fontStyle: 'italic', marginBottom: 10, lineHeight: 1.6,
              paddingBottom: 10, borderBottom: '1px solid var(--border)',
            }}>
              {plan.reasoning}
            </p>
          )}

          {/* Content */}
          {showThinking ? (
            <ThinkingDots />
          ) : (
            <div style={{
              color: 'var(--text-secondary)', fontSize: 13,
              lineHeight: 1.8,
            }}
              className={`markdown-body ${isStreaming && content ? 'streaming-cursor' : ''}`}
              dangerouslySetInnerHTML={{ __html: renderedContent }}
            />
          )}

          {/* Risk score breakdown */}
          {riskScore && (
            <Collapsible title="RISK SCORE BREAKDOWN" icon={BarChart3} defaultOpen>
              <ScoreBar label="Identity Confidence" value={riskScore.identity_confidence} />
              <ScoreBar label="Document Validity"   value={riskScore.document_validity}   />
              <div style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                paddingTop: 8, marginTop: 4, borderTop: '1px solid var(--border)',
              }}>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  Jurisdictional Risk
                </span>
                <RiskBadge tier={riskScore.jurisdictional_risk} />
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
                <span style={{ fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                  PEP Screening
                </span>
                <span style={{
                  fontSize: 10, fontFamily: 'var(--font-mono)',
                  color: riskScore.pep_screening === 'CLEAR' ? 'var(--success)' : 'var(--danger)',
                }}>
                  {riskScore.pep_screening}
                </span>
              </div>
              {riskScore.recommendation && (
                <p style={{
                  fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.5,
                  marginTop: 10, paddingTop: 8, borderTop: '1px solid var(--border)',
                }}>
                  {riskScore.recommendation}
                </p>
              )}
            </Collapsible>
          )}

          {/* Verdict row */}
          {verdict && riskScore && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginTop: 12,
              paddingTop: 12, borderTop: '1px solid var(--border)',
            }}>
              <span style={{ fontSize: 10, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                VERDICT
              </span>
              <VerdictBadge verdict={verdict} />
              <RiskBadge tier={riskScore.overall_risk_tier} />
            </div>
          )}
        </div>

        {/* Timestamp */}
        <p style={{
          fontSize: 10, color: 'var(--text-muted)',
          fontFamily: 'var(--font-mono)', marginTop: 4,
        }}>
          {formatTime(timestamp)}
        </p>
      </div>
    </div>
  )
}
