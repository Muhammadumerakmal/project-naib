import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Loader2, Pencil, X } from "lucide-react"
import { useState } from "react"
import { useOutletContext } from "react-router-dom"
import { decideApproval, listApprovals } from "../lib/api"
import type { ApprovalSummary, Decision } from "../lib/types"
import type { ClientOutletContext } from "./ClientLayout"

const REVIEWER_KEY = "naib.reviewer_name"

function useReviewerName(): [string, (v: string) => void] {
  const [name, setName] = useState(() => localStorage.getItem(REVIEWER_KEY) ?? "")
  return [
    name,
    (v: string) => {
      setName(v)
      localStorage.setItem(REVIEWER_KEY, v)
    },
  ]
}

function ApprovalCard({
  approval,
  clientId,
  token,
  reviewer,
}: {
  approval: ApprovalSummary
  clientId: string
  token: string
  reviewer: string
}) {
  const [expanded, setExpanded] = useState(false)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(approval.full_text)
  const qc = useQueryClient()

  const mutation = useMutation({
    mutationFn: (args: { decision: Decision; editedDraftMd?: string }) =>
      decideApproval(approval.id, token, {
        decidedBy: reviewer || "unknown reviewer",
        decision: args.decision,
        editedDraftMd: args.editedDraftMd,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["approvals", clientId] })
    },
  })

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="mb-1 flex items-center gap-2 text-xs font-medium text-slate-400">
            <span className="rounded bg-slate-100 px-2 py-0.5 uppercase tracking-wide">
              {approval.entity_type}
            </span>
            <span>{approval.action}</span>
            <span>{new Date(approval.requested_at).toLocaleString()}</span>
          </div>
          <p className="text-sm text-slate-800">
            {expanded ? null : approval.preview}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            type="button"
            onClick={() => setExpanded((e) => !e)}
            className="text-xs font-medium text-slate-500 underline"
          >
            {expanded ? "Collapse" : "Read full draft"}
          </button>
          <a
            href={`/clients/${clientId}/trace/${approval.lead_id}`}
            className="text-xs text-slate-400 underline"
          >
            View trace
          </a>
        </div>
      </div>

      {expanded && !editing && (
        <pre className="mt-3 whitespace-pre-wrap rounded-md bg-slate-50 p-3 text-sm text-slate-800">
          {approval.full_text}
        </pre>
      )}

      {editing && (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          rows={8}
          className="mt-3 w-full rounded-md border border-slate-300 p-3 text-sm"
        />
      )}

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate({ decision: "approved" })}
          className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-emerald-500 disabled:opacity-60"
        >
          <Check size={14} /> Approve
        </button>

        {editing ? (
          <button
            type="button"
            disabled={mutation.isPending}
            onClick={() => mutation.mutate({ decision: "edited", editedDraftMd: draft })}
            className="flex items-center gap-1.5 rounded-md bg-amber-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-amber-500 disabled:opacity-60"
          >
            <Pencil size={14} /> Save edit &amp; approve
          </button>
        ) : (
          <button
            type="button"
            onClick={() => {
              setExpanded(true)
              setEditing(true)
            }}
            className="flex items-center gap-1.5 rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <Pencil size={14} /> Edit
          </button>
        )}

        <button
          type="button"
          disabled={mutation.isPending}
          onClick={() => mutation.mutate({ decision: "rejected" })}
          className="flex items-center gap-1.5 rounded-md border border-red-300 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-60"
        >
          <X size={14} /> Reject
        </button>

        {mutation.isPending && <Loader2 size={16} className="animate-spin text-slate-400" />}
        {mutation.isError && (
          <span className="text-xs text-red-600">Couldn't save — try again.</span>
        )}
      </div>
    </div>
  )
}

export function ApprovalQueue() {
  const { client, token } = useOutletContext<ClientOutletContext>()
  const clientId = client.id
  const [reviewer, setReviewer] = useReviewerName()

  const { data: approvals, isLoading } = useQuery({
    queryKey: ["approvals", clientId],
    queryFn: () => listApprovals(clientId, token, { pendingOnly: true }),
  })

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-slate-900">Approval queue</h1>
        <label className="flex items-center gap-2 text-sm text-slate-500">
          Reviewing as
          <input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="your name"
            className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          />
        </label>
      </div>

      {isLoading && <Loader2 className="animate-spin text-slate-400" />}

      {approvals && approvals.length === 0 && (
        <p className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-500">
          Nothing waiting on you right now.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {approvals?.map((a) => (
          <ApprovalCard
            key={a.id}
            approval={a}
            clientId={clientId}
            token={token}
            reviewer={reviewer}
          />
        ))}
      </div>
    </div>
  )
}
