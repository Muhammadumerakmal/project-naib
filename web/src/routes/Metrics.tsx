import { useQuery } from "@tanstack/react-query"
import { Loader2, Lock, Unlock } from "lucide-react"
import { useParams } from "react-router-dom"
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts"
import { getClientAutonomy, getClientMetrics } from "../lib/api"

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-slate-900">{value}</p>
    </div>
  )
}

function ChartCard({
  title,
  data,
  valueFormatter,
}: {
  title: string
  data: { date: string; value: number }[]
  valueFormatter?: (v: number) => string
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="mb-2 text-sm font-medium text-slate-700">{title}</p>
      {data.length === 0 ? (
        <p className="py-8 text-center text-sm text-slate-400">Not enough data yet.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tick={{ fontSize: 12 }} />
            <YAxis tick={{ fontSize: 12 }} />
            <Tooltip
              formatter={(v) => {
                const n = Number(Array.isArray(v) ? v[0] : v)
                return valueFormatter ? valueFormatter(n) : n
              }}
            />
            <Line type="monotone" dataKey="value" stroke="#0f172a" strokeWidth={2} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}

function AutonomyPanel({ clientId }: { clientId: string }) {
  const { data: statuses } = useQuery({
    queryKey: ["autonomy", clientId],
    queryFn: () => getClientAutonomy(clientId),
  })

  if (!statuses || statuses.length === 0) return null

  return (
    <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="mb-1 text-sm font-medium text-slate-700">Graduated autonomy</p>
      <p className="mb-3 text-xs text-slate-400">
        Earned per action after {statuses[0].window_days} days of clean logs. Nothing sends
        automatically today regardless of this status — see CLAUDE.md rule 2.
      </p>
      <div className="flex flex-col gap-2">
        {statuses.map((s) => (
          <div key={s.action} className="flex items-center gap-2 text-sm">
            {s.eligible ? (
              <Unlock size={14} className="text-emerald-600" />
            ) : (
              <Lock size={14} className="text-slate-400" />
            )}
            <span className="font-medium text-slate-800">{s.action}</span>
            <span className="text-slate-400">{s.reason}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Metrics() {
  const { clientId = "" } = useParams<{ clientId: string }>()

  const { data: metrics, isLoading } = useQuery({
    queryKey: ["metrics", clientId],
    queryFn: () => getClientMetrics(clientId),
  })

  if (isLoading || !metrics) {
    return <Loader2 className="animate-spin text-slate-400" />
  }

  const responseTime =
    metrics.avg_time_to_first_response_seconds == null
      ? "—"
      : metrics.avg_time_to_first_response_seconds < 120
        ? `${Math.round(metrics.avg_time_to_first_response_seconds)}s`
        : `${Math.round(metrics.avg_time_to_first_response_seconds / 60)}m`

  return (
    <div>
      <h1 className="mb-4 text-lg font-semibold text-slate-900">Metrics</h1>

      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Injections blocked" value={String(metrics.injections_blocked_total)} />
        <StatCard label="Avg. time to first response" value={responseTime} />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <ChartCard
          title="Edit rate over time"
          data={metrics.edit_rate_over_time}
          valueFormatter={(v) => `${Math.round(v * 100)}%`}
        />
        <ChartCard
          title="Cost per lead over time"
          data={metrics.cost_per_lead_over_time}
          valueFormatter={(v) => `$${v.toFixed(3)}`}
        />
      </div>

      <AutonomyPanel clientId={clientId} />
    </div>
  )
}
