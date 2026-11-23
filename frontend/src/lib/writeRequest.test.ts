import { afterEach, expect, it, vi } from 'vitest'
import { createPendingWrite, loadPendingWrite, savePendingWrite } from './pendingWrite'
import { submitWrite } from './writeRequest'

afterEach(() => { sessionStorage.clear(); vi.unstubAllGlobals() })

it('retries an uncertain write with its original actor, path, body and key', async () => {
  const write = createPendingWrite('alice@east.test', '/api/certificates/11/revoke', {})
  const requests: Array<{ path: string; email: string | null; key: string | null; body: string | null }> = []
  let attempt = 0
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    requests.push({ path, email: new Headers(options.headers).get('X-Actor-Email'), key: new Headers(options.headers).get('Idempotency-Key'), body: options.body as string })
    attempt++
    if (attempt === 1) throw new Error('network timeout')
    return new Response(JSON.stringify({ operation_id: 9, certificate_id: 11, status: 'REVOKED', changed: true }), { status: 200 })
  }))
  await expect(submitWrite(write)).rejects.toThrow('network timeout')
  expect(loadPendingWrite()?.key).toBe(write.key)
  await submitWrite(loadPendingWrite()!)
  expect(requests).toEqual([
    { path: '/api/certificates/11/revoke', email: 'alice@east.test', key: write.key, body: '{}' },
    { path: '/api/certificates/11/revoke', email: 'alice@east.test', key: write.key, body: '{}' },
  ])
  expect(loadPendingWrite()).toBeNull()
})

it('uses a new key for a new operation and keeps a conflicting write pending', async () => {
  const first = createPendingWrite('alice@east.test', '/api/courses/1/bulk-issue', {})
  const second = createPendingWrite('alice@east.test', '/api/courses/1/bulk-issue', {})
  expect(first.key).not.toBe(second.key)
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ message: 'key conflict' }), { status: 409 })))
  await expect(submitWrite(first)).rejects.toThrow('key conflict')
  expect(loadPendingWrite()?.key).toBe(first.key)
})

it('keeps an unresolved write to another resource when one write completes', async () => {
  const first = createPendingWrite('alice@east.test', '/api/certificates/11/revoke', {})
  const second = createPendingWrite('alice@east.test', '/api/certificates/12/revoke', {})
  savePendingWrite(first)
  savePendingWrite(second)
  vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ operation_id: 8, certificate_id: 12, status: 'REVOKED', changed: true }), { status: 200 })))
  await submitWrite(second)
  expect(loadPendingWrite('alice@east.test', first.path)?.key).toBe(first.key)
  expect(loadPendingWrite('alice@east.test', second.path)).toBeNull()
})
