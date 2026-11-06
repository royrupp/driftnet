import { useEffect } from 'react'
import { useWebSocket } from './hooks/useWebSocket'
import { useEventStore } from './stores/eventStore'
import { useAlertStore } from './stores/alertStore'
import { AgentCard } from './components/AgentCard'
import { AlertsPanel } from './components/AlertsPanel'
import { EventFeed } from './components/EventFeed'
import { EventChart } from './components/EventChart'
import { StatsBar } from './components/StatsBar'
import { AttackTimeline } from './components/AttackTimeline'

export default function App() {
  const fetchRecentEvents = useEventStore((s) => s.fetchRecent)
  const fetchRecentAlerts = useAlertStore((s) => s.fetchRecent)

  // Connect WebSocket (reconnects automatically on disconnect)
  useWebSocket(`ws://${window.location.host}/ws`)

  // Seed stores on initial load
  useEffect(() => {
    fetchRecentEvents()
    fetchRecentAlerts()
  }, [fetchRecentEvents, fetchRecentAlerts])

  return (
    <div className="min-h-screen p-4 flex flex-col gap-4">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-gray-800 pb-3">
        <span className="text-red-500 text-lg">⬟</span>
        <h1 className="text-white font-bold tracking-widest text-sm uppercase">Driftnet</h1>
        <span className="text-gray-600 text-xs ml-auto">Security Monitor</span>
      </header>

      {/* Live stats */}
      <StatsBar />

      {/* Agent status */}
      <AgentCard />

      {/* Main content: Alerts + Events side by side */}
      <div className="flex gap-4 flex-1 min-h-0" style={{ height: '55vh' }}>
        <div className="w-2/5">
          <AlertsPanel />
        </div>
        <div className="w-3/5">
          <EventFeed />
        </div>
      </div>

      {/* Attack timeline */}
      <AttackTimeline />

      {/* Sparkline chart */}
      <EventChart />
    </div>
  )
}
