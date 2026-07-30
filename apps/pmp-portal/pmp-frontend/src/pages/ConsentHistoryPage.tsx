import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function ConsentHistoryPage() {
  const { data } = useQuery({
    queryKey: ['consent-history'],
    queryFn: async () => (await api.get('/consent/history?days=90')).data,
  })
  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <h1>Consent History</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </main>
  )
}
