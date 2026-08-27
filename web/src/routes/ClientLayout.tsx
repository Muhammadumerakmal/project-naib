import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { Navigate, Outlet, useParams } from "react-router-dom"
import { KillSwitch } from "../components/KillSwitch"
import { Nav } from "../components/Nav"
import { ApiError, getClient } from "../lib/api"

export function ClientLayout() {
  const { clientId } = useParams<{ clientId: string }>()

  const { data: client, isLoading, error } = useQuery({
    queryKey: ["client", clientId],
    queryFn: () => getClient(clientId!),
    enabled: !!clientId,
  })

  if (!clientId) return <Navigate to="/" replace />

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  if (error || !client) {
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 text-slate-600">
        <p>{notFound ? "No client found with that ID." : "Couldn't reach Naib's API."}</p>
        <a href="/" className="text-sm text-slate-900 underline">
          Back to start
        </a>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <KillSwitch client={client} />
      <Nav clientId={clientId} />
      <main className="mx-auto max-w-5xl px-6 py-6">
        <Outlet context={{ client }} />
      </main>
    </div>
  )
}
