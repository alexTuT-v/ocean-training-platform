import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
import { getJson } from '../api/client'
import type { MeResponse, Tenant } from '../api/types'

type ActorState = { actorEmail: string; tenant: Tenant | null; generation: number; loading: boolean; error: string | null; writeInFlight: boolean; setWriteInFlight: (busy: boolean) => void; switchActor: (email: string) => void; retry: () => void }
const ActorContext = createContext<ActorState | null>(null)

export function ActorProvider({ children }: { children: ReactNode }) {
  const [actorEmail, setActorEmail] = useState('alice@east.test')
  const [tenant, setTenant] = useState<Tenant | null>(null)
  const [generation, setGeneration] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [writeInFlight, setWriteInFlight] = useState(false)
  const requestId = useRef(0)

  useEffect(() => {
    const id = ++requestId.current
    const controller = new AbortController()
    setLoading(true); setError(null); setTenant(null)
    getJson<MeResponse>('/api/me', actorEmail, controller.signal).then(data => {
      if (id === requestId.current) { setTenant(data.tenant); setLoading(false) }
    }).catch(cause => {
      if (id !== requestId.current || controller.signal.aborted) return
      setError(cause instanceof Error ? cause.message : '无法确认管理员身份'); setLoading(false)
    })
    return () => { controller.abort(); requestId.current++ }
  }, [actorEmail, generation])

  const switchActor = useCallback((email: string) => {
    if (!writeInFlight && email !== actorEmail) { setTenant(null); setLoading(true); setActorEmail(email); setGeneration(value => value + 1) }
  }, [actorEmail, writeInFlight])
  const retry = useCallback(() => setGeneration(value => value + 1), [])
  return <ActorContext.Provider value={{ actorEmail, tenant, generation, loading, error, writeInFlight, setWriteInFlight, switchActor, retry }}>{children}</ActorContext.Provider>
}

export function useActor(): ActorState {
  const context = useContext(ActorContext)
  if (!context) throw new Error('ActorProvider is missing')
  return context
}
