import { Navigate, Route, Routes } from "react-router-dom"
import { ApprovalQueue } from "./routes/ApprovalQueue"
import { ClientLayout } from "./routes/ClientLayout"
import { Escalations } from "./routes/Escalations"
import { Landing } from "./routes/Landing"
import { Metrics } from "./routes/Metrics"
import { TraceViewer } from "./routes/TraceViewer"

export function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/clients/:clientId" element={<ClientLayout />}>
        <Route index element={<Navigate to="approvals" replace />} />
        <Route path="approvals" element={<ApprovalQueue />} />
        <Route path="escalations" element={<Escalations />} />
        <Route path="metrics" element={<Metrics />} />
        <Route path="trace" element={<TraceViewer />} />
        <Route path="trace/:leadId" element={<TraceViewer />} />
      </Route>
    </Routes>
  )
}
