import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function WebhooksPage() {
  const { data } = useQuery({
    queryKey: ['webhooks'],
    queryFn: async () => (await api.get('/admin/webhook')).data,
  })
  return (
    <main style={{ padding: 24 }}>
      <h1>Webhook Integrations</h1>
      <p>Push consent state and banner configs to Salesforce, HubSpot, Outreach, Highspot.</p>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </main>
  )
}
