import { useEffect, useRef, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

/** Live updates via WebSocket. Reconnects with backoff; degrades silently. */
export function useRealtimeSync() {
  const qc = useQueryClient()
  const [connected, setConnected] = useState(false)
  const retry = useRef(0)

  useEffect(() => {
    let ws: WebSocket | null = null
    let timer: ReturnType<typeof setTimeout>
    let closed = false

    function open() {
      const token = sessionStorage.getItem('access_token')
      if (!token) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/v1?token=${token}`)

      ws.onopen = () => { setConnected(true); retry.current = 0 }
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'consent.updated') {
          qc.invalidateQueries({ queryKey: ['preferences'] })
          qc.invalidateQueries({ queryKey: ['history'] })
        }
        if (msg.type === 'dsar.created') qc.invalidateQueries({ queryKey: ['dsar'] })
      }
      ws.onclose = () => {
        setConnected(false)
        if (closed) return
        // Exponential backoff, capped — a dead socket shouldn't hammer the server
        const delay = Math.min(1000 * 2 ** retry.current++, 30000)
        timer = setTimeout(open, delay)
      }
    }

    open()
    return () => { closed = true; clearTimeout(timer); ws?.close() }
  }, [qc])

  return { connected }
}
