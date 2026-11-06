import { useEffect, useState } from 'react'
import { useAlertStore } from '../stores/alertStore'

interface Metrics {
  events_per_minute: number
  avg_alert_latency_ms: number | null
  agent_cpu_percent: number | null
  agent_memory_mb: number | null
}

export function StatsBar() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const alerts = useAlertStore((s) => s.alerts)

  useEffect(() => {
    const fetch_ = async () => {
      try {
        const res = await fetch('/api/metrics')
        setMetrics(await res.json())
      } catch {}
    }
    fetch_()
    const id = setInterval(fetch_, 5000)
    return () => clearInterval(id)
  }, [])

  const today = new Date().toDateString()
  const alertsToday = alerts.filter((a) => new Date(a.ts).toDateString() === today).length

  const ruleCounts = alerts.reduce<Record<string, number>>((acc, a) => {
    acc[a.rule_id] = (acc[a.rule_id] ?? 0) + 1
    return acc
  }, {})
  const topRule = Object.entries(ruleCounts).sort((a, b) => b[1] - a[1])[0]

  const stats = [
    { label: 'Events / min', value: metrics?.events_per_minute ?? '—', accent: 'text-cyan-400' },
    { label: 'Alerts today', value: alertsToday, accent: alertsToday > 0 ? 'text-orange-400' : 'text-white' },
    {
      label: 'Avg latency',
      value: metrics?.avg_alert_latency_ms != null ? `${Math.round(metrics.avg_alert_latency_ms)}ms` : '—',
      accent: 'text-white',
    },
    {
      label: 'Top rule',
      value: topRule ? `${topRule[0].replace(/_/g, ' ')} ×${topRule[1]}` : '—',
      accent: 'text-yellow-400',
    },
    {
      label: 'Agent CPU',
      value: metrics?.agent_cpu_percent != null ? `${metrics.agent_cpu_percent.toFixed(1)}%` : '—',
      accent: 'text-white',
    },
    {
      label: 'Agent Mem',
      value: metrics?.agent_memory_mb != null ? `${metrics.agent_memory_mb} MB` : '—',
      accent: 'text-white',
    },
  ]

  return (
    <div className="grid grid-cols-6 gap-3">
      {stats.map(({ label, value, accent }) => (
        <div key={label} className="bg-gray-900 border border-gray-700 rounded-lg px-4 py-3">
          <div className="text-xs text-gray-500 uppercase tracking-wide">{label}</div>
          <div className={`font-mono font-bold text-lg mt-1 truncate ${accent}`}>{String(value)}</div>
        </div>
      ))}
    </div>
  )
}
