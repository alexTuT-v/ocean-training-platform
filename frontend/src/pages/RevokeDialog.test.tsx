import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RevokeDialog } from './RevokeDialog'
import { createPendingWrite, loadPendingWrite, savePendingWrite } from '../lib/pendingWrite'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })

it('requires confirmation and labels an already revoked result without claiming a new change', async () => {
  const paths: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    paths.push(path)
    return new Response(JSON.stringify({ operation_id: 3, certificate_id: 11, status: 'REVOKED', changed: false }), { status: 200 })
  }))
  render(<RevokeDialog id={11} serial="CERT-E-011" actorEmail="alice@east.test" onDone={() => {}} onClose={() => {}} />)
  expect(screen.getByText('CERT-E-011')).toBeTruthy()
  expect(paths).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
  expect(await screen.findByText('证书已撤销，无需重复操作')).toBeTruthy()
  expect(screen.queryByText('撤销成功')).toBeNull()
  expect(paths).toEqual(['/api/certificates/11/revoke'])
})

it('focuses the confirmation action and closes with Escape', () => {
  const onClose = vi.fn()
  render(<RevokeDialog id={11} serial="CERT-E-011" actorEmail="alice@east.test" onDone={() => {}} onClose={onClose} />)
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '确认撤销' }))
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(onClose).toHaveBeenCalledOnce()
})

it('lets a confirmed key conflict be discarded without clearing another pending operation', async () => {
  const other = createPendingWrite('alice@east.test', '/api/certificates/12/revoke', {})
  savePendingWrite(other)
  const keys: string[] = []
  const onClose = vi.fn()
  vi.stubGlobal('fetch', vi.fn(async (_path: string, options: RequestInit) => {
    keys.push(new Headers(options.headers).get('Idempotency-Key') ?? '')
    return new Response(JSON.stringify({ code: 'IDEMPOTENCY_CONFLICT', message: 'key conflict' }), { status: 409 })
  }))
  const { unmount } = render(<RevokeDialog id={11} serial="CERT-E-011" actorEmail="alice@east.test" onDone={() => {}} onClose={onClose} />)
  fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
  expect(await screen.findByText('key conflict')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '放弃冲突操作' }))
  expect(onClose).toHaveBeenCalledOnce()
  expect(loadPendingWrite('alice@east.test', '/api/certificates/11/revoke')).toBeNull()
  expect(loadPendingWrite('alice@east.test', '/api/certificates/12/revoke')?.key).toBe(other.key)
  unmount()
  render(<RevokeDialog id={11} serial="CERT-E-011" actorEmail="alice@east.test" onDone={() => {}} onClose={onClose} />)
  fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
  expect(keys).toHaveLength(2)
  expect(keys[1]).not.toBe(keys[0])
})
