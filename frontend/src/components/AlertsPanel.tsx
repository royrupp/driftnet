import { useState } from 'react'
import type { Alert } from '../types'
import { useAlertStore } from '../stores/alertStore'
import { AlertDetail } from './AlertDetail'

const SEVERITY_CLASSES: Record<string, string> = {
  critical: 'bg-red-600 text-white',
  high: 'bg-orange-600 text-white',
  medium: 'bg-yellow-600 text-black',
  low: 'bg-blue-600 text-white',
}

function formatTs(ts: string): string {
  return new Date(ts).toLocaleTimeString()
}

export function AlertsPanel() {
  const alerts = useAlertStore((s) => s.alerts)
  const clearAlerts = useAlertStore((s) => s.clearAlerts)
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null)

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Alerts</h2>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{alerts.length} total</span>
          {alerts.length > 0 && (
            <button
              onClick={() => clearAlerts()}
              className="text-xs text-gray-500 hover:text-red-400 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">
        {alerts.length === 0 ? (
          <div className="p-4 text-gray-500 text-sm italic">No alerts yet — waiting for detections...</div>
        ) : (
          alerts.map((alert) => (
            <div
              key={alert.id}
              onClick={() => setSelectedAlert(alert)}
              className="px-4 py-3 border-b border-gray-800 hover:bg-gray-800 cursor-pointer flex items-start gap-3"
            >
              <span className={`text-xs font-bold px-2 py-0.5 rounded shrink-0 ${SEVERITY_CLASSES[alert.severity] ?? 'bg-gray-600 text-white'}`}>
                {alert.severity.toUpperCase()}
              </span>
              <div className="flex-1 min-w-0">
                <div className="text-white text-sm truncate">{alert.description ?? alert.rule_id}</div>
                <div className="flex items-center gap-2 mt-1">
                  {alert.mitre_id && (
                    <span className="text-xs bg-gray-700 text-cyan-400 px-1.5 py-0.5 rounded font-mono">
                      {alert.mitre_id}
                    </span>
                  )}
                  <span className="text-xs text-gray-500">{formatTs(alert.ts)}</span>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
      <AlertDetail alert={selectedAlert} onClose={() => setSelectedAlert(null)} />
    </div>
  )
}
