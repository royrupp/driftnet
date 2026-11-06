import { useEffect, useState } from 'react'
import type { Alert } from '../types'

interface Props {
  alert: Alert | null
  onClose: () => void
}

export function AlertDetail({ alert, onClose }: Props) {
  const [detail, setDetail] = useState<Alert | null>(null)

  useEffect(() => {
    if (!alert) { setDetail(null); return }
    setDetail(alert) // show immediately from store
    // then fetch fresh (picks up llm_report if Phase 5 has populated it)
    fetch(`/api/alerts/${alert.id}`)
      .then((r) => r.json())
      .then((data) => setDetail(data))
      .catch(() => {/* keep store version */})
  }, [alert?.id])

  if (!alert) return null

  const d = detail ?? alert

  return (
    <div
      className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-gray-900 border border-gray-700 rounded-xl max-w-2xl w-full max-h-[80vh] overflow-y-auto p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="text-white font-semibold text-lg">{d.description ?? d.rule_id}</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-400">{d.host}</span>
              {d.mitre_id && (
                <span className="text-xs bg-gray-700 text-cyan-400 px-1.5 py-0.5 rounded font-mono">
                  {d.mitre_id}
                </span>
              )}
              <span className="text-xs text-gray-500">{new Date(d.ts).toLocaleString()}</span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white text-xl leading-none ml-4"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        <div className="mb-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-1">Related Events</div>
          {d.related_event_ids.length === 0 ? (
            <div className="text-gray-500 text-sm italic">None</div>
          ) : (
            <div className="text-gray-300 text-sm font-mono">
              IDs: {d.related_event_ids.join(', ')}
            </div>
          )}
        </div>

        <div>
          <div className="text-xs text-gray-500 uppercase tracking-wide mb-2">AI Investigation</div>
          {d.llm_report ? (
            <div className="space-y-2 text-sm">
              {d.llm_report.status === 'unavailable' ? (
                <div className="text-gray-500 italic">Ollama unavailable: {d.llm_report.reason}</div>
              ) : (
                <>
                  {d.llm_report.summary && <p className="text-gray-200">{d.llm_report.summary}</p>}
                  {d.llm_report.techniques && d.llm_report.techniques.length > 0 && (
                    <div>
                      <div className="text-gray-500 text-xs mb-1">Techniques</div>
                      <ul className="list-disc list-inside text-gray-300 text-xs space-y-0.5">
                        {d.llm_report.techniques.map((t, i) => <li key={i}>{t}</li>)}
                      </ul>
                    </div>
                  )}
                  {d.llm_report.next_steps && d.llm_report.next_steps.length > 0 && (
                    <div>
                      <div className="text-gray-500 text-xs mb-1">Next Steps</div>
                      <ul className="list-disc list-inside text-gray-300 text-xs space-y-0.5">
                        {d.llm_report.next_steps.map((s, i) => <li key={i}>{s}</li>)}
                      </ul>
                    </div>
                  )}
                </>
              )}
            </div>
          ) : (
            <div className="text-gray-500 text-sm italic">Investigation pending...</div>
          )}
        </div>
      </div>
    </div>
  )
}
