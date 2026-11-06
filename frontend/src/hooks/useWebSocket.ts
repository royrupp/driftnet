import { useEffect, useRef, useCallback } from 'react'
import { useAgentStore } from '../stores/agentStore'
import { useEventStore } from '../stores/eventStore'
import { useAlertStore } from '../stores/alertStore'

const BASE_DELAY = 1000
const MAX_DELAY = 30000

export function useWebSocket(path: string) {
  const wsRef = useRef<WebSocket | null>(null)
  const attemptRef = useRef(0)
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const shouldReconnect = useRef(true)

  const setAgent = useAgentStore((s) => s.setAgent)
  const fetchRecentEvents = useEventStore((s) => s.fetchRecent)
  const fetchRecentAlerts = useAlertStore((s) => s.fetchRecent)
  const clearAlertsLocal = useAlertStore((s) => s.clearLocal)

  const connect = useCallback(() => {
    if (!shouldReconnect.current) return
    const ws = new WebSocket(path)
    wsRef.current = ws

    ws.onopen = () => {
      attemptRef.current = 0
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)
        switch (msg.type) {
          case 'agent_status':
            setAgent(msg.data)
            break
          case 'new_events':
            fetchRecentEvents()
            break
          case 'new_alert':
            fetchRecentAlerts()
            break
          case 'alerts_cleared':
            clearAlertsLocal()
            break
        }
      } catch {
        // malformed message — ignore
      }
    }

    ws.onclose = () => {
      if (!shouldReconnect.current) return
      const delay = Math.min(BASE_DELAY * Math.pow(2, attemptRef.current), MAX_DELAY)
      const jitter = Math.random() * 1000
      timerRef.current = setTimeout(() => {
        attemptRef.current += 1
        connect()
      }, delay + jitter)
    }

    ws.onerror = () => ws.close()
  }, [path, setAgent, fetchRecentEvents, fetchRecentAlerts])

  useEffect(() => {
    shouldReconnect.current = true
    connect()
    return () => {
      shouldReconnect.current = false
      if (timerRef.current) clearTimeout(timerRef.current)
      wsRef.current?.close(1000, 'unmount')
    }
  }, [connect])
}
