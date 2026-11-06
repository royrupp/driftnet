import { create } from 'zustand'
import type { Event } from '../types'

interface EventState {
  events: Event[]
  fetchRecent: () => Promise<void>
}

export const useEventStore = create<EventState>((set) => ({
  events: [],
  fetchRecent: async () => {
    try {
      const res = await fetch('/api/events?limit=100')
      const data = await res.json()
      set({ events: data.events ?? [] })
    } catch {
      // backend not ready yet — ignore
    }
  },
}))
