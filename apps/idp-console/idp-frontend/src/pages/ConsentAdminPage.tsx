import { ClipboardList } from 'lucide-react'
import { EmptyState } from '@sentinel/ui'
import { ConsoleShell, PageHeader } from '../components/ConsoleShell'

export default function ConsentAdminPage() {
  return (
    <ConsoleShell>
      <PageHeader title="Consents"
        description="Search and manage consent records across every source system." />
      <EmptyState icon={ClipboardList} title="Consent search"
        description="Cross-system consent search and manual override land with the integrations work (A3)." />
    </ConsoleShell>
  )
}
