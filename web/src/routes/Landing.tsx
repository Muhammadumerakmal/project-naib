import { useState } from "react"
import { useNavigate } from "react-router-dom"

// A pasted full link (…/clients/<id>?token=<token>) or a bare id — either
// way we pull out a client_id and, if present, a token.
function parseDashboardLink(input: string): { clientId: string; token: string | null } | null {
  const trimmed = input.trim()
  if (!trimmed) return null

  try {
    const url = new URL(trimmed, window.location.origin)
    const match = url.pathname.match(/\/clients\/([^/]+)/)
    if (match) {
      return { clientId: match[1], token: url.searchParams.get("token") }
    }
  } catch {
    // Not a URL -- fall through and treat it as a bare client id below.
  }
  return { clientId: trimmed, token: null }
}

/** No login yet — Phase 8 owns onboarding/auth. Each client is handed a
 * bookmarked magic link (`/clients/<id>?token=<token>`) by their Naib
 * contact at onboarding; this screen exists as the recovery path for
 * someone who lost that link or opened the bare domain, not as real auth
 * on its own. */
export function Landing() {
  const [link, setLink] = useState("")
  const [token, setToken] = useState("")
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          const parsed = parseDashboardLink(link)
          if (!parsed) return
          const finalToken = parsed.token ?? token.trim()
          if (!finalToken) return
          navigate(`/clients/${parsed.clientId}?token=${encodeURIComponent(finalToken)}`)
        }}
        className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="mb-1 text-lg font-semibold text-slate-900">Naib</h1>
        <p className="mb-4 text-sm text-slate-500">
          Paste the dashboard link your Naib contact sent you — or your client ID and access
          token separately below.
        </p>
        <input
          value={link}
          onChange={(e) => setLink(e.target.value)}
          placeholder="dashboard link or client id"
          className="mb-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <input
          value={token}
          onChange={(e) => setToken(e.target.value)}
          placeholder="access token (skip if your link already had one)"
          className="mb-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Open dashboard
        </button>
        <p className="mt-3 text-center text-xs text-slate-400">
          Lost both? Ask your Naib contact to resend your link.
        </p>
      </form>
    </div>
  )
}
