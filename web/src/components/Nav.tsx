import { AlertCircle, BarChart3, CheckSquare } from "lucide-react"
import { NavLink } from "react-router-dom"

const linkBase =
  "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors"
const linkActive = "bg-slate-900 text-white"
const linkInactive = "text-slate-600 hover:bg-slate-100"

export function Nav({ clientId }: { clientId: string }) {
  return (
    <nav className="flex gap-1 border-b border-slate-200 bg-white px-6 py-2">
      <NavLink
        to={`/clients/${clientId}/approvals`}
        className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}
      >
        <CheckSquare size={16} />
        Approvals
      </NavLink>
      <NavLink
        to={`/clients/${clientId}/escalations`}
        className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}
      >
        <AlertCircle size={16} />
        Escalations
      </NavLink>
      <NavLink
        to={`/clients/${clientId}/metrics`}
        className={({ isActive }) => `${linkBase} ${isActive ? linkActive : linkInactive}`}
      >
        <BarChart3 size={16} />
        Metrics
      </NavLink>
    </nav>
  )
}
