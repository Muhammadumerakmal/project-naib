// Mirrors src/naib/schemas/*.py and naib/store/models.py exactly — keep in
// sync by hand (Phase 7 has no shared codegen yet; see PLAN.md Phase 8 for
// whether that's worth adding once there's a second client).

export interface ClientDetail {
  id: string
  name: string
  plan: string
  autonomy_level: string
  kill_switch: boolean
}

export type Decision = "approved" | "edited" | "rejected"

export interface ApprovalSummary {
  id: string
  entity_type: "proposal" | "followup"
  entity_id: string
  action: string
  lead_id: string
  requested_at: string
  decided_at: string | null
  decided_by: string | null
  decision: Decision | null
  preview: string
  full_text: string
}

export interface Escalation {
  id: string
  lead_id: string
  reason: string
  brief_md: string
  assigned_to: string | null
  resolved_at: string | null
  created_at: string
}

export interface MetricsPoint {
  date: string
  value: number
}

export interface ClientMetrics {
  edit_rate_over_time: MetricsPoint[]
  cost_per_lead_over_time: MetricsPoint[]
  injections_blocked_total: number
  avg_time_to_first_response_seconds: number | null
}

export interface AutonomyStatus {
  client_id: string
  action: string
  window_days: number
  days_tracked: number
  decided_count: number
  approved_count: number
  edited_count: number
  rejected_count: number
  edit_or_reject_rate: number
  eligible: boolean
  reason: string
}

export interface TraceQualification {
  score: number
  band: string
  reasons: string[]
  disqualifiers: string[]
  model: string | null
}

export interface TraceProposal {
  id: string
  playbook_entry_id: string
  price_band: string
  version: number
  approved_by: string | null
  approved_at: string | null
}

export interface TraceEscalation {
  reason: string
  created_at: string
}

export interface TraceFollowup {
  attempt_number: number
  created_at: string
}

export interface TraceApproval {
  entity_type: string
  action: string
  decision: string | null
  decided_by: string | null
  decided_at: string | null
}

export interface TraceEvent {
  run_id: string
  agent: string
  event_type: string
  tool: string | null
  guardrail: string | null
  outcome: string | null
  model: string | null
  tokens_in: number | null
  tokens_out: number | null
  cost_usd: number | null
  latency_ms: number | null
  created_at: string
}

export interface LeadTrace {
  lead_id: string
  client_id: string
  channel: string
  status: string
  language: string | null
  confidence: number | null
  created_at: string
  qualifications: TraceQualification[]
  proposals: TraceProposal[]
  escalations: TraceEscalation[]
  followups: TraceFollowup[]
  approvals: TraceApproval[]
  events: TraceEvent[]
}

export interface SignedTraceBundle {
  trace: LeadTrace
  signature: string
  algorithm: string
  signed_at: string
}
