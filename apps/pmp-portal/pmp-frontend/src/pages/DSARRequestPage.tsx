import { useState } from 'react'
import { api } from '../services/api'

export default function DSARRequestPage() {
  const [requestType, setRequestType] = useState('access')
  const [description, setDescription] = useState('')
  const [result, setResult] = useState<string | null>(null)

  const submit = async () => {
    const res = await api.post('/dsar/request', { request_type: requestType, description })
    setResult(`Request submitted. ID: ${res.data.id}. Due: ${res.data.due_date}`)
  }

  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: 24 }}>
      <h1>Data Subject Access Request</h1>
      <select value={requestType} onChange={(e) => setRequestType(e.target.value)}>
        <option value="access">Access my data</option>
        <option value="deletion">Delete my data</option>
        <option value="rectification">Correct my data</option>
        <option value="export">Export my data</option>
        <option value="portability">Data portability</option>
      </select>
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Describe your request…"
        rows={4}
        style={{ display: 'block', width: '100%', marginTop: 12 }}
      />
      <button onClick={submit} style={{ marginTop: 12 }}>Submit Request</button>
      {result && <p>{result}</p>}
    </main>
  )
}
