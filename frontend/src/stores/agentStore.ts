import { create } from 'zustand'
import type { AgentStatus } from '../types'

interface AgentState {
  agent: AgentStatus | null
  setAgent: (agent: AgentStatus) => void
}

export const useAgentStore = create<AgentState>((set) => ({
  agent: null,
  setAgent: (agent) => set({ agent }),
}))
