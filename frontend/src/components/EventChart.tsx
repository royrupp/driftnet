import { useMemo } from 'react'
import { AreaChart, Area, XAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { useEventStore } from '../stores/eventStore'

interface Bucket {
  minute: string
  count: number
}

export function EventChart() {
  const events = useEventStore((s) => s.events)

  const buckets = useMemo((): Bucket[] => {
    const now = Date.now()
    const map: Record<string, number> = {}
    // Create 5-minute buckets (every 1 minute)
    for (let i = 4; i >= 0; i--) {
      const t = new Date(now - i * 60_000)
      const key = t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      map[key] = 0
    }
    for (const e of events) {
      const t = new Date(e.ts)
      if (now - t.getTime() > 5 * 60_000) continue
      const key = t.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      if (key in map) map[key]++
    }
    return Object.entries(map).map(([minute, count]) => ({ minute, count }))
  }, [events])

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 p-3">
      <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">Events / min (last 5 min)</div>
      <div className="h-20">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={buckets} margin={{ top: 4, right: 8, left: -32, bottom: 0 }}>
            <XAxis dataKey="minute" tick={{ fontSize: 10, fill: '#6b7280' }} tickLine={false} axisLine={false} />
            <Tooltip
              contentStyle={{ background: '#111827', border: '1px solid #374151', fontSize: 11 }}
              labelStyle={{ color: '#9ca3af' }}
              itemStyle={{ color: '#22d3ee' }}
            />
            <Area
              type="monotone"
              dataKey="count"
              stroke="#22d3ee"
              fill="#164e63"
              strokeWidth={2}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
