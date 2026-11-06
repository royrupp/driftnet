import { render, screen } from '@testing-library/react'
import { AgentCard } from '../AgentCard'
import { useAgentStore } from '../../stores/agentStore'

describe('AgentCard', () => {
  it('shows waiting message when no agent', () => {
    useAgentStore.setState({ agent: null })
    render(<AgentCard />)
    expect(screen.getByText(/waiting for agent/i)).toBeInTheDocument()
  })

  it('shows hostname when agent is connected', () => {
    useAgentStore.setState({
      agent: {
        agent_id: 'test',
        hostname: 'my-macbook',
        last_seen: new Date().toISOString(),
        is_connected: true,
      },
    })
    render(<AgentCard />)
    expect(screen.getByText('my-macbook')).toBeInTheDocument()
    expect(screen.getByText(/connected/i)).toBeInTheDocument()
  })
})
