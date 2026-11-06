import { render, screen } from '@testing-library/react'
import { AlertsPanel } from '../AlertsPanel'
import { useAlertStore } from '../../stores/alertStore'

describe('AlertsPanel', () => {
  it('shows empty state when no alerts', () => {
    useAlertStore.setState({ alerts: [] })
    render(<AlertsPanel />)
    expect(screen.getByText(/no alerts yet/i)).toBeInTheDocument()
  })

  it('renders alert row with severity badge', () => {
    useAlertStore.setState({
      alerts: [{
        id: 1,
        ts: new Date().toISOString(),
        host: 'test-host',
        rule_id: 'unusual_listener',
        severity: 'high',
        description: 'Unusual listener on port 4444',
        mitre_id: 'T1571',
        related_event_ids: [],
        llm_report: null,
      }],
    })
    render(<AlertsPanel />)
    expect(screen.getByText(/unusual listener on port 4444/i)).toBeInTheDocument()
    expect(screen.getByText('HIGH')).toBeInTheDocument()
    expect(screen.getByText('T1571')).toBeInTheDocument()
  })
})
