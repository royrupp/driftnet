import { useMemo } from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from 'recharts'
import { useAlertStore } from '../stores/alertStore'
import { useEventStore } from '../stores/eventStore'

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#dc2626',
  high: '#ea580c',
  medium: '#ca8a04',
  low: '#2563eb',
}

const WINDOW_MS = 15 * 60 * 1000

function formatTime(ms: number) {
  return new Date(ms).toLocaleTimeString()
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: Record<string, string | number> }> }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div className="bg-gray-800 border border-gray-600 rounded p-2 text-xs max-w-xs shadow-lg">
      <div className="text-gray-400">{formatTime(d.x as number)}</div>
      <div className="text-white font-semibold">{String(d.label)}</div>
      {d.detail && <div className="text-gray-300 truncate">{String(d.detail)}</div>}
    </div>
  )
}

export function AttackTimeline() {
  const alerts = useAlertStore((s) => s.alerts)
  const events = useEventStore((s) => s.events)

  const now = Date.now()
  const windowStart = now - WINDOW_MS

  const eventPoints = useMemo(
    () =>
      events
        .filter((e) => new Date(e.ts).getTime() > windowStart)
        .map((e) => ({
          x: new Date(e.ts).getTime(),
          y: 0.25,
          label: e.event_type.replace(/_/g, ' '),
          detail: e.process_name ?? e.remote_ip ?? '',
        })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [events]
  )

  const alertPoints = useMemo(
    () =>
      alerts
        .filter((a) => new Date(a.ts).getTime() > windowStart)
        .map((a) => ({
          x: new Date(a.ts).getTime(),
          y: 0.75,
          severity: a.severity,
          label: a.rule_id.replace(/_/g, ' '),
          detail: a.description ?? '',
        })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [alerts]
  )

  const hasData = eventPoints.length > 0 || alertPoints.length > 0

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-4">
      <div className="flex items-center justify-between mb-2">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Attack Timeline</h2>
        <span className="text-xs text-gray-500">Last 15 min</span>
      </div>
      <div className="flex items-center gap-5 mb-3">
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-gray-600 inline-block" />
          Events ({eventPoints.length})
        </span>
        <span className="flex items-center gap-1.5 text-xs text-gray-500">
          <span className="w-2 h-2 rounded-full bg-orange-500 inline-block" />
          Alerts ({alertPoints.length})
        </span>
      </div>
      {!hasData ? (
        <div className="h-24 flex items-center justify-center text-gray-600 text-sm italic">
          No activity in the last 15 minutes
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={100}>
          <ScatterChart margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
            <XAxis
              dataKey="x"
              type="number"
              domain={[windowStart, now]}
              tickFormatter={formatTime}
              tick={{ fill: '#6b7280', fontSize: 10 }}
              tickCount={6}
              scale="time"
            />
            <YAxis dataKey="y" type="number" domain={[0, 1]} hide />
            <Tooltip content={<CustomTooltip />} />
            <Scatter data={eventPoints} fill="#4b5563">
              {eventPoints.map((_, i) => (
                <Cell key={i} fill="#4b5563" r={3} />
              ))}
            </Scatter>
            <Scatter data={alertPoints}>
              {alertPoints.map((p, i) => (
                <Cell key={i} fill={SEVERITY_COLORS[p.severity] ?? '#6b7280'} r={6} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
