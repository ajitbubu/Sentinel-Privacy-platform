import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function AuditPage() {
  const { data } = useQuery({
    queryKey: ['audit'],
    queryFn: async () => (await api.get('/admin/audit')).data,
  })
  return (
    <main style={{ padding: 24 }}>
      <h1>Audit Trail (Immutable)</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </main>
  )
}
