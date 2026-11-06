import { render, screen } from '@testing-library/react'
import { EventFeed } from '../EventFeed'
import { useEventStore } from '../../stores/eventStore'

describe('EventFeed', () => {
  it('shows empty state when no events', () => {
    useEventStore.setState({ events: [] })
    render(<EventFeed />)
    expect(screen.getByText(/no events yet/i)).toBeInTheDocument()
  })

  it('renders event row with truncated cmdline', () => {
    useEventStore.setState({
      events: [{
        id: 1,
        ts: new Date().toISOString(),
        host: 'test-host',
        event_type: 'process_start',
        process_name: 'bash',
        cmdline: 'bash -c "echo hello world from a very long command line that exceeds sixty characters in length"',
      }],
    })
    render(<EventFeed />)
    expect(screen.getByText('bash')).toBeInTheDocument()
    // cmdline is truncated to 60 chars + ellipsis
    const cell = screen.getByText(/bash -c "echo hello world from a very long command/)
    expect(cell.textContent).toMatch(/…$/)
  })
})
