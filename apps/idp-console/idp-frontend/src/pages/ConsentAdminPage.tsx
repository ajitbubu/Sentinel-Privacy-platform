import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function ConsentAdminPage() {
  const { data } = useQuery({
    queryKey: ['admin-consents'],
    queryFn: async () => (await api.get('/admin/consent')).data,
  })
  return (
    <main style={{ padding: 24 }}>
      <h1>Consent Administration</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
      {/* TODO: searchable table + DPO override modal (requires reason, audit-logged) */}
    </main>
  )
}
