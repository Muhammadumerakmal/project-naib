import type {
  ApprovalSummary,
  AutonomyStatus,
  ClientDetail,
  ClientMetrics,
  Decision,
  Escalation,
  SignedTraceBundle,
} from "./types"

// No auth/multi-origin story yet — that's Phase 8's onboarding flow. Every
// client gets a URL with their client_id in it (see routes/Landing.tsx).
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  })
  if (!res.ok) {
    const body = await res.text()
    throw new ApiError(res.status, body || res.statusText)
  }
  return (await res.json()) as T
}

export function getClient(clientId: string): Promise<ClientDetail> {
  return request(`/clients/${clientId}`)
}

export function setKillSwitch(clientId: string, enabled: boolean): Promise<ClientDetail> {
  return request(`/clients/${clientId}/kill-switch`, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  })
}

export function listApprovals(
  clientId: string,
  opts: { entityType?: string; pendingOnly?: boolean } = {},
): Promise<ApprovalSummary[]> {
  const params = new URLSearchParams()
  if (opts.entityType) params.set("entity_type", opts.entityType)
  params.set("pending_only", String(opts.pendingOnly ?? true))
  return request(`/clients/${clientId}/approvals?${params.toString()}`)
}

export function listEscalations(clientId: string): Promise<Escalation[]> {
  return request(`/clients/${clientId}/escalations`)
}

export function getClientMetrics(clientId: string): Promise<ClientMetrics> {
  return request(`/clients/${clientId}/metrics`)
}

export function getClientAutonomy(clientId: string): Promise<AutonomyStatus[]> {
  return request(`/clients/${clientId}/autonomy`)
}

export function decideApproval(
  approvalId: string,
  body: {
    decidedBy: string
    decision: Decision
    editDiff?: string
    editedDraftMd?: string
  },
): Promise<{ status: string }> {
  return request(`/approvals/${approvalId}/decide`, {
    method: "POST",
    body: JSON.stringify({
      decided_by: body.decidedBy,
      decision: body.decision,
      edit_diff: body.editDiff ?? null,
      edited_draft_md: body.editedDraftMd ?? null,
    }),
  })
}

export function getLeadTrace(leadId: string): Promise<SignedTraceBundle> {
  return request(`/leads/${leadId}/trace`)
}
