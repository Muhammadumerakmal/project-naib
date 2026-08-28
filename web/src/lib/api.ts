import type {
  ApprovalSummary,
  AutonomyStatus,
  ClientDetail,
  ClientMetrics,
  Decision,
  Escalation,
  SignedTraceBundle,
} from "./types"

// No user-account system yet -- that's Phase 8's onboarding-issued
// per-client bearer token (naib.dashboard_auth), threaded through every
// call below explicitly rather than held as hidden global state.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000"

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...init?.headers,
    },
  })
  if (!res.ok) {
    const body = await res.text()
    throw new ApiError(res.status, body || res.statusText)
  }
  return (await res.json()) as T
}

export function getClient(clientId: string, token: string): Promise<ClientDetail> {
  return request(`/clients/${clientId}`, token)
}

export function setKillSwitch(
  clientId: string,
  enabled: boolean,
  token: string,
): Promise<ClientDetail> {
  return request(`/clients/${clientId}/kill-switch`, token, {
    method: "POST",
    body: JSON.stringify({ enabled }),
  })
}

export function listApprovals(
  clientId: string,
  token: string,
  opts: { entityType?: string; pendingOnly?: boolean } = {},
): Promise<ApprovalSummary[]> {
  const params = new URLSearchParams()
  if (opts.entityType) params.set("entity_type", opts.entityType)
  params.set("pending_only", String(opts.pendingOnly ?? true))
  return request(`/clients/${clientId}/approvals?${params.toString()}`, token)
}

export function listEscalations(clientId: string, token: string): Promise<Escalation[]> {
  return request(`/clients/${clientId}/escalations`, token)
}

export function getClientMetrics(clientId: string, token: string): Promise<ClientMetrics> {
  return request(`/clients/${clientId}/metrics`, token)
}

export function getClientAutonomy(clientId: string, token: string): Promise<AutonomyStatus[]> {
  return request(`/clients/${clientId}/autonomy`, token)
}

export function decideApproval(
  approvalId: string,
  token: string,
  body: {
    decidedBy: string
    decision: Decision
    editDiff?: string
    editedDraftMd?: string
  },
): Promise<{ status: string }> {
  return request(`/approvals/${approvalId}/decide`, token, {
    method: "POST",
    body: JSON.stringify({
      decided_by: body.decidedBy,
      decision: body.decision,
      edit_diff: body.editDiff ?? null,
      edited_draft_md: body.editedDraftMd ?? null,
    }),
  })
}

export function getLeadTrace(leadId: string, token: string): Promise<SignedTraceBundle> {
  return request(`/leads/${leadId}/trace`, token)
}
