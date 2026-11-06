import { useEventStore } from '../stores/eventStore'

const EVENT_TYPE_CLASSES: Record<string, string> = {
  process_start: 'bg-green-900 text-green-300',
  network_conn: 'bg-blue-900 text-blue-300',
  auth_event: 'bg-purple-900 text-purple-300',
}

function formatTs(ts: string): string {
  return new Date(ts).toLocaleTimeString()
}

export function EventFeed() {
  const events = useEventStore((s) => s.events)

  return (
    <div className="bg-gray-900 rounded-lg border border-gray-700 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-300 uppercase tracking-wide">Live Events</h2>
        <span className="text-xs text-gray-500">{events.length} loaded</span>
      </div>
      <div className="flex-1 overflow-y-auto">
        {events.length === 0 ? (
          <div className="p-4 text-gray-500 text-sm italic">
            No events yet — start the agent with <code className="text-green-400">sudo python3 agent/agent.py</code>
          </div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="text-gray-500 text-left border-b border-gray-800">
                <th className="px-3 py-2 font-normal">Time</th>
                <th className="px-3 py-2 font-normal">Type</th>
                <th className="px-3 py-2 font-normal">Process</th>
                <th className="px-3 py-2 font-normal">Detail</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id} className="border-b border-gray-800 hover:bg-gray-800">
                  <td className="px-3 py-1.5 text-gray-500 whitespace-nowrap">{formatTs(event.ts)}</td>
                  <td className="px-3 py-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${EVENT_TYPE_CLASSES[event.event_type] ?? 'bg-gray-700 text-gray-300'}`}>
                      {event.event_type}
                    </span>
                  </td>
                  <td className="px-3 py-1.5 text-gray-300">{event.process_name ?? '—'}</td>
                  <td className="px-3 py-1.5 text-gray-400 max-w-xs truncate">
                    {event.cmdline
                      ? event.cmdline.slice(0, 60) + (event.cmdline.length > 60 ? '…' : '')
                      : event.local_port
                      ? `${event.local_ip ?? '*'}:${event.local_port}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
