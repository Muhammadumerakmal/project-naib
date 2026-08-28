import { useQuery } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useEffect } from "react"
import { Navigate, Outlet, useParams, useSearchParams } from "react-router-dom"
import { KillSwitch } from "../components/KillSwitch"
import { Nav } from "../components/Nav"
import { ApiError, getClient } from "../lib/api"
import { getStoredToken, setStoredToken } from "../lib/auth"
import type { ClientDetail } from "../lib/types"

export interface ClientOutletContext {
  client: ClientDetail
  token: string
}

export function ClientLayout() {
  const { clientId } = useParams<{ clientId: string }>()
  const [searchParams, setSearchParams] = useSearchParams()
  const urlToken = searchParams.get("token")
  // Derived synchronously, not effect-driven state: a magic-link `?token=`
  // wins while present, otherwise fall back to what's already stored.
  const token = clientId ? (urlToken ?? getStoredToken(clientId)) : null

  // Side effect only: persist a magic-link token, then strip it from the
  // URL -- it shouldn't linger in browser history or a Referer header.
  // Once stripped, urlToken is null next render and this becomes a no-op.
  useEffect(() => {
    if (!clientId || !urlToken) return
    setStoredToken(clientId, urlToken)
    const next = new URLSearchParams(searchParams)
    next.delete("token")
    setSearchParams(next, { replace: true })
  }, [clientId, urlToken, searchParams, setSearchParams])

  const { data: client, isLoading, error } = useQuery({
    queryKey: ["client", clientId],
    queryFn: () => getClient(clientId!, token!),
    enabled: !!clientId && !!token,
  })

  if (!clientId) return <Navigate to="/" replace />

  if (!token) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 px-4 text-center text-slate-600">
        <p>This link is missing its access token.</p>
        <p className="text-sm text-slate-400">
          Ask your Naib contact to resend your dashboard link.
        </p>
      </div>
    )
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-slate-400">
        <Loader2 className="animate-spin" />
      </div>
    )
  }

  if (error || !client) {
    const unauthorized = error instanceof ApiError && error.status === 401
    const notFound = error instanceof ApiError && error.status === 404
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-2 px-4 text-center text-slate-600">
        <p>
          {unauthorized
            ? "That access token isn't valid for this client. Ask your Naib contact to resend your link."
            : notFound
              ? "No client found with that ID."
              : "Couldn't reach Naib's API."}
        </p>
        <a href="/" className="text-sm text-slate-900 underline">
          Back to start
        </a>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <KillSwitch client={client} token={token} />
      <Nav clientId={clientId} />
      <main className="mx-auto max-w-5xl px-6 py-6">
        <Outlet context={{ client, token } satisfies ClientOutletContext} />
      </main>
    </div>
  )
}
