// ── Dev toggle ────────────────────────────────────────────────────────────────
// Set to true to use mock API endpoints and data for frontend development without invoking the agent.
export const USE_MOCK = true

// ── API endpoints ─────────────────────────────────────────────────────────────
export const ENDPOINTS = {
  newSession:   () => '/chat/session',
  chat:         (sid) => `/chat/${sid}`,
  stream:       (sid) => `/chat/${sid}/stream`,
  mockStream:   () => '/chat/mock/stream',
  history:      (sid) => `/chat/${sid}/history`,
}

// ── Intent display config ─────────────────────────────────────────────────────
export const INTENT_CONFIG = {
  generic_compliance: { label: 'Compliance Q&A',   color: '#6c8fff' },
  document_analysis:  { label: 'Document Analysis', color: '#f59e0b' },
  kyc_check:          { label: 'KYC Check',         color: '#4ade80' },
  hybrid:             { label: 'Hybrid Analysis',   color: '#c9a84c' },
  insufficient_info:  { label: 'More Info Needed',  color: '#8b92a5' },
}

// ── Pipeline step keys ────────────────────────────────────────────────────────
export const PIPELINE_STEPS = [
  { key: 'doc',    label: 'Document Analysis'    },
  { key: 'reg',    label: 'Regulatory Retrieval' },
  { key: 'risk',   label: 'Risk Scoring'         },
  { key: 'report', label: 'Generating Response'  },
]

// ── Welcome screen suggestions ────────────────────────────────────────────────
export const SUGGESTIONS = [
  { text: 'What are the CDD requirements under MAS Notice 626?',      icon: 'book' },
  { text: 'Perform a full KYC check on this customer.',               icon: 'shield' },
  { text: 'What enhanced due diligence applies to PEPs in Singapore?', icon: 'alert' },
  { text: 'Analyse the documents I will attach.',                     icon: 'file' },
]

// ── File upload limits ────────────────────────────────────────────────────────
export const MAX_FILES     = 5
export const ACCEPTED_TYPES = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']