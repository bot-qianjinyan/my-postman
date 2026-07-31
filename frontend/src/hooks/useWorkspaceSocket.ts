import { useEffect, useRef, useState } from 'react'
import { getToken } from '../api/client'
import type { OnlineUser } from '../api/types'

type Handler = (event: Record<string, unknown>) => void

export function useWorkspaceSocket(workspaceId: number | null, onEvent: Handler) {
  const [online, setOnline] = useState<OnlineUser[]>([])
  const [connected, setConnected] = useState(false)
  const handlerRef = useRef(onEvent)
  handlerRef.current = onEvent

  useEffect(() => {
    if (!workspaceId) return
    const token = getToken()
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(
      `${protocol}://${window.location.host}/ws/workspaces/${workspaceId}?token=${encodeURIComponent(token)}`,
    )

    ws.onopen = () => setConnected(true)
    ws.onclose = () => setConnected(false)
    ws.onerror = () => setConnected(false)
    ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data) as Record<string, unknown>
        if (event.type === 'presence.join' || event.type === 'presence.leave') {
          setOnline((event.online as OnlineUser[]) || [])
        }
        handlerRef.current(event)
      } catch {
        /* ignore */
      }
    }

    const ping = window.setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) ws.send('ping')
    }, 25000)

    return () => {
      window.clearInterval(ping)
      ws.close()
    }
  }, [workspaceId])

  return { online, connected }
}
