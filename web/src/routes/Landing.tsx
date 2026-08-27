import { useState } from "react"
import { useNavigate } from "react-router-dom"

/** No login yet — Phase 8 owns onboarding/auth. Each client is handed a
 * bookmarked URL (`/clients/<their-id>/approvals`); this screen exists so
 * the link is guessable/typeable during the pilot, not as real auth. */
export function Landing() {
  const [clientId, setClientId] = useState("")
  const navigate = useNavigate()

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (clientId.trim()) navigate(`/clients/${clientId.trim()}/approvals`)
        }}
        className="w-full max-w-sm rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
      >
        <h1 className="mb-1 text-lg font-semibold text-slate-900">Naib</h1>
        <p className="mb-4 text-sm text-slate-500">Enter your client ID to open your dashboard.</p>
        <input
          value={clientId}
          onChange={(e) => setClientId(e.target.value)}
          placeholder="client id"
          className="mb-3 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
        />
        <button
          type="submit"
          className="w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-700"
        >
          Open dashboard
        </button>
      </form>
    </div>
  )
}
