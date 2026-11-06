import { useAgentStore } from '../stores/agentStore'

function timeAgo(ts: string): string {
  const utc = ts.endsWith('Z') || ts.includes('+') ? ts : ts + 'Z'
  const diff = Math.floor((Date.now() - new Date(utc).getTime()) / 1000)
  if (diff < 60) return `${diff}s ago`
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
  return `${Math.floor(diff / 3600)}h ago`
}

export function AgentCard() {
  const agent = useAgentStore((s) => s.agent)

  if (!agent) {
    return (
      <div className="bg-gray-900 rounded-lg p-4 border border-gray-700 text-gray-500 text-sm">
        Waiting for agent... run <code className="text-green-400">sudo python3 agent/agent.py</code>
      </div>
    )
  }

  return (
    <div className="bg-gray-900 rounded-lg p-4 border border-gray-700 flex items-center gap-6">
      <div>
        <div className="text-xs text-gray-500 uppercase tracking-wide">Agent</div>
        <div className="text-white font-semibold">{agent.hostname}</div>
        <div className="text-gray-400 text-xs">{agent.os_version}</div>
      </div>
      <div>
        {agent.is_connected ? (
          <span className="inline-flex items-center gap-1 text-green-400 text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-green-400 inline-block animate-pulse" />
            Connected
          </span>
        ) : (
          <span className="inline-flex items-center gap-1 text-red-400 text-sm font-medium">
            <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
            Disconnected
          </span>
        )}
        <div className="text-gray-500 text-xs mt-1">Last seen: {timeAgo(agent.last_seen)}</div>
      </div>
      <div className="ml-auto text-right text-xs text-gray-400">
        <div>CPU: {agent.cpu_percent?.toFixed(1) ?? '—'}%</div>
        <div>Mem: {agent.memory_mb?.toFixed(0) ?? '—'} MB</div>
      </div>
    </div>
  )
}
