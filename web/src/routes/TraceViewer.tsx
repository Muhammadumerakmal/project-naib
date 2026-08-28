import { useQuery } from "@tanstack/react-query"
import { Loader2, ShieldCheck } from "lucide-react"
import { useState } from "react"
import { useNavigate, useOutletContext, useParams } from "react-router-dom"
import { getLeadTrace } from "../lib/api"
import type { ClientOutletContext } from "./ClientLayout"

function fmtCost(cost: number | null): string {
  return cost == null ? "—" : `US$${cost.toFixed(4)}`
}

/** Every step, guardrail outcome, and cost for one lead, in plain language
 * — PLAN.md Phase 7 / CLAUDE.md rule 3 ("if a client asks why did it say
 * that, we answer with a record"). */
export function TraceViewer() {
  const { leadId } = useParams<{ leadId?: string }>()
  const { client, token } = useOutletContext<ClientOutletContext>()
  const clientId = client.id
  const navigate = useNavigate()
  const [inputLeadId, setInputLeadId] = useState("")

  const { data: bundle, isLoading, error } = useQuery({
    queryKey: ["trace", leadId],
    queryFn: () => getLeadTrace(leadId!, token),
    enabled: !!leadId,
  })

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold text-slate-900">Trace viewer</h1>

      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (inputLeadId.trim()) navigate(`/clients/${clientId}/trace/${inputLeadId.trim()}`)
        }}
        className="mb-4 flex gap-2"
      >
        <input
          value={inputLeadId}
          onChange={(e) => setInputLeadId(e.target.value)}
          placeholder="lead id"
          className="w-80 rounded-md border border-slate-300 px-3 py-1.5 text-sm"
        />
        <button
          type="submit"
          className="rounded-md bg-slate-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-slate-700"
        >
          Look up
        </button>
      </form>

      {!leadId && (
        <p className="text-sm text-slate-500">
          Paste a lead ID above, or follow a "View full trace" link from an escalation.
        </p>
      )}

      {isLoading && <Loader2 className="animate-spin text-slate-400" />}
      {error && <p className="text-sm text-red-600">Couldn't find a trace for that lead.</p>}

      {bundle && (
        <div className="flex flex-col gap-4">
          <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white p-4 text-xs text-slate-500 shadow-sm">
            <ShieldCheck size={14} className="text-emerald-600" />
            Signed with {bundle.algorithm} at {new Date(bundle.signed_at).toLocaleString()} —
            verifiable with <code>naib.trace_export.verify_trace</code>.
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-700">
              <strong>Channel:</strong> {bundle.trace.channel} &nbsp;
              <strong>Status:</strong> {bundle.trace.status} &nbsp;
              <strong>Language:</strong> {bundle.trace.language ?? "—"} &nbsp;
              <strong>Confidence:</strong> {bundle.trace.confidence ?? "—"}
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Received {new Date(bundle.trace.created_at).toLocaleString()}
            </p>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="mb-2 text-sm font-medium text-slate-700">Timeline</p>
            <ol className="flex flex-col gap-2">
              {bundle.trace.events.map((event, i) => (
                <li
                  key={`${event.run_id}-${i}`}
                  className="border-l-2 border-slate-200 pl-3 text-sm"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-medium text-slate-800">{event.agent}</span>
                    <span className="text-slate-400">{event.event_type}</span>
                    {event.tool && (
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs">
                        tool: {event.tool}
                      </span>
                    )}
                    {event.guardrail && (
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs ${
                          event.outcome === "blocked"
                            ? "bg-red-100 text-red-700"
                            : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        guardrail: {event.guardrail} ({event.outcome})
                      </span>
                    )}
                    <span className="text-xs text-slate-400">{fmtCost(event.cost_usd)}</span>
                    <span className="text-xs text-slate-400">
                      {event.latency_ms != null ? `${event.latency_ms}ms` : ""}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400">
                    {new Date(event.created_at).toLocaleString()}
                  </p>
                </li>
              ))}
            </ol>
          </div>

          {bundle.trace.escalations.length > 0 && (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 shadow-sm">
              <p className="mb-1 text-sm font-medium text-amber-800">Escalations</p>
              {bundle.trace.escalations.map((e, i) => (
                <p key={i} className="text-sm text-amber-800">
                  {e.reason} — {new Date(e.created_at).toLocaleString()}
                </p>
              ))}
            </div>
          )}

          {bundle.trace.proposals.length > 0 && (
            <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-1 text-sm font-medium text-slate-700">Proposals</p>
              {bundle.trace.proposals.map((p) => (
                <p key={p.id} className="text-sm text-slate-700">
                  {p.playbook_entry_id} · {p.price_band} · v{p.version}
                  {p.approved_by ? ` · approved by ${p.approved_by}` : " · pending approval"}
                </p>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
