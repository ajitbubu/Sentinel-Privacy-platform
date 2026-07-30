import { useQuery } from '@tanstack/react-query'
import { api } from '../services/api'

export default function DSARAdminPage() {
  const { data } = useQuery({
    queryKey: ['admin-dsar'],
    queryFn: async () => (await api.get('/admin/dsar')).data,
  })
  return (
    <main style={{ padding: 24 }}>
      <h1>DSAR Management</h1>
      <pre>{JSON.stringify(data, null, 2)}</pre>
      {/* TODO: fulfillment workflow - review data, generate export, deliver */}
    </main>
  )
}
