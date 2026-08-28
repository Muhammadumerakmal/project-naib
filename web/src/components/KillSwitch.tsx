import { useMutation, useQueryClient } from "@tanstack/react-query"
import { AlertTriangle, Loader2, Square } from "lucide-react"
import { useState } from "react"
import { setKillSwitch } from "../lib/api"
import type { ClientDetail } from "../lib/types"

/** Always-visible, unmissable per PLAN.md Phase 7: "Kill switch, visible and
 * unmissable" and the phase gate — "a non-technical person ... stops a run,
 * unaided." One click opens a plain-language confirm, second click acts. */
export function KillSwitch({ client, token }: { client: ClientDetail; token: string }) {
  const [confirming, setConfirming] = useState(false)
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: (enabled: boolean) => setKillSwitch(client.id, enabled, token),
    onSuccess: (updated) => {
      qc.setQueryData(["client", client.id], updated)
      setConfirming(false)
    },
  })

  const isStopped = client.kill_switch

  if (isStopped) {
    return (
      <div className="flex items-center justify-between gap-4 border-b border-red-800 bg-red-900 px-6 py-3 text-white">
        <div className="flex items-center gap-2 font-medium">
          <AlertTriangle size={18} />
          Naib is stopped for {client.name}. No new leads are being worked.
        </div>
        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate(false)}
          className="flex items-center gap-2 rounded-md bg-white px-4 py-2 font-semibold text-red-900 hover:bg-red-100 disabled:opacity-60"
        >
          {mutation.isPending && <Loader2 size={16} className="animate-spin" />}
          Resume Naib
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center justify-between gap-4 border-b border-emerald-800 bg-emerald-800 px-6 py-3 text-white">
      <span className="font-medium">Naib is running for {client.name}.</span>

      {confirming ? (
        <div className="flex items-center gap-3">
          <span className="text-sm">Stop every run for this client, right now?</span>
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate(true)}
            className="flex items-center gap-2 rounded-md bg-white px-4 py-2 font-semibold text-red-900 hover:bg-red-100 disabled:opacity-60"
          >
            {mutation.isPending && <Loader2 size={16} className="animate-spin" />}
            Yes, stop it
          </button>
          <button
            type="button"
            onClick={() => setConfirming(false)}
            className="rounded-md border border-white/40 px-3 py-2 text-sm hover:bg-white/10"
          >
            Cancel
          </button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setConfirming(true)}
          className="flex items-center gap-2 rounded-md bg-red-700 px-4 py-2 font-semibold hover:bg-red-600"
        >
          <Square size={16} />
          Stop everything
        </button>
      )}
    </div>
  )
}
