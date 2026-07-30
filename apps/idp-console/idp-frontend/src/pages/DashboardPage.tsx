export default function DashboardPage() {
  return (
    <main style={{ padding: 24 }}>
      <h1>IDP Console</h1>
      <nav style={{ display: 'flex', gap: 16 }}>
        <a href="/banners">Banner Builder</a>
        <a href="/consents">Consent Admin</a>
        <a href="/dsar">DSAR Requests</a>
        <a href="/audit">Audit Trail</a>
        <a href="/webhooks">Webhooks</a>
      </nav>
      {/* TODO: KPI cards - consent rates, pending DSARs, sync latency, webhook health */}
    </main>
  )
}
