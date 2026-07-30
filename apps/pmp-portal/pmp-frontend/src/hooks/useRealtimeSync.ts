import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

/** Subscribes to WebSocket; invalidates queries when consent/banner events arrive (<1s sync). */
export function useRealtimeSync() {
  const qc = useQueryClient()
  useEffect(() => {
    const token = sessionStorage.getItem('access_token') ?? ''
    const ws = new WebSocket(`${location.origin.replace('http', 'ws')}/ws/v1?token=${token}`)
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.channel?.includes('consent')) qc.invalidateQueries({ queryKey: ['consents'] })
      if (msg.channel?.includes('banner')) qc.invalidateQueries({ queryKey: ['banner'] })
    }
    return () => ws.close()
  }, [qc])
}
