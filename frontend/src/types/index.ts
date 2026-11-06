export interface Event {
  id: number
  ts: string
  host: string
  event_type: 'process_start' | 'network_conn' | 'auth_event'
  process_name?: string
  pid?: number
  ppid?: number
  username?: string
  cmdline?: string
  local_ip?: string
  local_port?: number
  remote_ip?: string
  remote_port?: number
  raw_json?: unknown
}

export interface LlmReport {
  summary?: string
  timeline?: string[]
  severity?: string
  techniques?: string[]
  next_steps?: string[]
  status?: string
  reason?: string
}

export interface Alert {
  id: number
  ts: string
  host: string
  rule_id: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  description?: string
  mitre_id?: string
  related_event_ids: number[]
  llm_report?: LlmReport | null
}

export interface AgentStatus {
  agent_id: string
  hostname: string
  os_version?: string
  agent_version?: string
  last_seen: string
  is_connected: boolean
  cpu_percent?: number
  memory_mb?: number
}
