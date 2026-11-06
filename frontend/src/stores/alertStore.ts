import { create } from 'zustand'
import type { Alert } from '../types'

interface AlertState {
  alerts: Alert[]
  fetchRecent: () => Promise<void>
  clearAlerts: () => Promise<void>
  clearLocal: () => void
}

export const useAlertStore = create<AlertState>((set) => ({
  alerts: [],
  fetchRecent: async () => {
    try {
      const res = await fetch('/api/alerts?limit=50')
      const data = await res.json()
      set({ alerts: data.alerts ?? [] })
    } catch {
      // backend not ready yet — ignore
    }
  },
  clearAlerts: async () => {
    try {
      await fetch('/api/alerts', { method: 'DELETE' })
      set({ alerts: [] })
    } catch {
      // ignore
    }
  },
  clearLocal: () => set({ alerts: [] }),
}))
