import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { ActorProvider, useActor } from './ActorProvider'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

function Probe() {
  const { actorEmail, tenant, switchActor } = useActor()
  return <div><span>{actorEmail}</span><span>{tenant?.name ?? 'Loading'}</span><button onClick={() => switchActor('bob@west.test')}>Switch to Bob</button></div>
}

it('ignores an Alice response that arrives after switching to Bob', async () => {
  let resolveAlice!: (value: Response) => void
  const alice = new Promise<Response>(resolve => { resolveAlice = resolve })
  const requests: string[] = []
  vi.stubGlobal('fetch', vi.fn((_path: string, options: RequestInit) => {
    const email = new Headers(options.headers).get('X-Actor-Email') ?? ''
    requests.push(email)
    if (email === 'alice@east.test') return alice
    return Promise.resolve({ ok: true, json: async () => ({ admin: { id: 2, email }, tenant: { id: 2, name: 'West', timezone: 'Australia/Perth' } }) } as Response)
  }))

  render(<ActorProvider><Probe /></ActorProvider>)
  fireEvent.click(screen.getByRole('button', { name: 'Switch to Bob' }))
  expect(await screen.findByText('West')).toBeTruthy()
  resolveAlice({ ok: true, json: async () => ({ admin: { id: 1, email: 'alice@east.test' }, tenant: { id: 1, name: 'East', timezone: 'Australia/Sydney' } }) } as Response)
  await Promise.resolve()
  expect(screen.queryByText('East')).toBeNull()
  expect(requests).toContain('bob@west.test')
})
