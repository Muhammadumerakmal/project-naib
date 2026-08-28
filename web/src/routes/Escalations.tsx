import { useQuery } from "@tanstack/react-query"
import { AlertCircle, Loader2 } from "lucide-react"
import { useOutletContext } from "react-router-dom"
import { listEscalations } from "../lib/api"
import type { ClientOutletContext } from "./ClientLayout"

export function Escalations() {
  const { client, token } = useOutletContext<ClientOutletContext>()
  const clientId = client.id

  const { data: escalations, isLoading } = useQuery({
    queryKey: ["escalations", clientId],
    queryFn: () => listEscalations(clientId, token),
  })

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold text-slate-900">Escalations</h1>

      {isLoading && <Loader2 className="animate-spin text-slate-400" />}

      {escalations && escalations.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          No escalations. Naib is handling everything within its confidence threshold.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {escalations?.map((e) => (
          <div
            key={e.id}
            className="rounded-lg border border-amber-200 bg-amber-50 p-4 shadow-sm"
          >
            <div className="mb-1 flex items-center gap-2 text-xs font-medium text-amber-700">
              <AlertCircle size={14} />
              {e.reason}
              <span className="text-amber-500">
                · {new Date(e.created_at).toLocaleString()}
              </span>
              {e.resolved_at && (
                <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-700">
                  resolved
                </span>
              )}
            </div>
            <p className="whitespace-pre-wrap text-sm text-slate-800">{e.brief_md}</p>
            <a
              href={`/clients/${clientId}/trace/${e.lead_id}`}
              className="mt-2 inline-block text-xs font-medium text-slate-500 underline"
            >
              View full trace for this lead
            </a>
          </div>
        ))}
      </div>
    </div>
  )
}
