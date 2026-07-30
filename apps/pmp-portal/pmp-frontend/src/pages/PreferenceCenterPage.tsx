import { usePreferenceCenter } from '../hooks/useConsent'
import { useRealtimeSync } from '../hooks/useRealtimeSync'

export default function PreferenceCenterPage() {
  const { data, isLoading } = usePreferenceCenter()
  useRealtimeSync()

  if (isLoading) return <div>Loading preferences…</div>

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <h1>Privacy Preference Center</h1>
      <p>Manage how we communicate with you across every channel.</p>
      <pre>{JSON.stringify(data, null, 2)}</pre>
      {/* TODO: render purposes x channels toggle grid */}
    </main>
  )
}
