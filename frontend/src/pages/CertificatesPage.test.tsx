import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { ActorProvider } from '../actor/ActorProvider'
import { CertificatesPage } from './CertificatesPage'
import { createPendingWrite, savePendingWrite } from '../lib/pendingWrite'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })
const me = { admin: { id: 1, email: 'alice@east.test' }, tenant: { id: 1, name: 'East', timezone: 'Australia/Sydney' } }
const item = { id: 11, serial_number: 'CERT-E-011', learner_name: 'Alex Lee', course_title: 'Safety 101', issued_local_date: '2026-01-11', status: 'ACTIVE' }
const detail = { ...item, issued_local_datetime: '2026-01-11 00:30' }

function Location() { const location = useLocation(); return <output data-testid="location">{location.search}</output> }
function json(body: unknown, status = 200) { return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } }) }

it('keeps list filters in the URL and displays the server local date in detail', async () => {
  const paths: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    paths.push(path)
    if (path === '/api/me') return json(me)
    if (path === '/api/certificates/11') return json(detail)
    return json({ items: [item], page: 3, page_size: 20, total: 55 })
  }))
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/certificates?page=3']}><ActorProvider><CertificatesPage /><Location /></ActorProvider></MemoryRouter>)
  expect(await screen.findByText('CERT-E-011')).toBeTruthy()
  expect(screen.getByText('2026-01-11')).toBeTruthy()
  fireEvent.change(screen.getByRole('searchbox', { name: '搜索学员或序列号' }), { target: { value: 'Alex' } })
  await waitFor(() => expect(screen.getByTestId('location').textContent).toContain('page=1'))
  await waitFor(() => expect(paths.some(path => path.includes('search=Alex'))).toBe(true))
  fireEvent.change(screen.getByRole('combobox', { name: '排序字段' }), { target: { value: 'learner_name' } })
  await waitFor(() => expect(paths.some(path => path.includes('sort=learner_name'))).toBe(true))
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  await waitFor(() => expect(paths.some(path => path.includes('page=2'))).toBe(true))
  fireEvent.click(screen.getByRole('button', { name: /CERT-E-011/ }))
  expect(await screen.findByText('2026-01-11 00:30')).toBeTruthy()
})

it('shows empty and error states with a retry action', async () => {
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    calls++
    return calls === 1 ? json({ message: '暂时无法加载' }, 500) : json({ items: [], page: 1, page_size: 20, total: 0 })
  }))
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ActorProvider><CertificatesPage /></ActorProvider></MemoryRouter>)
  expect(await screen.findByRole('alert')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '重试列表' }))
  expect(await screen.findByText('暂无证书')).toBeTruthy()
})

it('exports the filters visible in the certificate page without pagination', async () => {
  const requests: Array<{ path: string; email: string | null }> = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    requests.push({ path, email: new Headers(options.headers).get('X-Actor-Email') })
    if (path === '/api/me') return json(me)
    if (path.startsWith('/api/certificates/export?')) return new Response('learner,course\n', { status: 200 })
    return json({ items: [item], page: 3, page_size: 20, total: 55 })
  }))
  Object.defineProperty(URL, 'createObjectURL', { value: vi.fn(() => 'blob:test'), configurable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: vi.fn(), configurable: true })
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }} initialEntries={['/certificates?search=Alex&sort=learner_name&direction=asc&page=3']}><ActorProvider><CertificatesPage /></ActorProvider></MemoryRouter>)
  expect(await screen.findByText('CERT-E-011')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '导出 CSV' }))
  await waitFor(() => expect(requests.some(request => request.path === '/api/certificates/export?search=Alex&sort=learner_name&direction=asc' && request.email === 'alice@east.test')).toBe(true))
})

it('returns focus to the revoke button after closing its confirmation', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/certificates/11') return json(detail)
    return json({ items: [item], page: 1, page_size: 20, total: 1 })
  }))
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ActorProvider><CertificatesPage /></ActorProvider></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: 'CERT-E-011' }))
  const revoke = await screen.findByRole('button', { name: '撤销证书' })
  fireEvent.click(revoke)
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(revoke)
})

it.each([[true, '撤销成功'], [false, '证书已撤销，无需重复操作']] as const)('keeps the revoke outcome visible while detail refreshes (changed=%s)', async (changed, message) => {
  let detailCalls = 0
  let resolveRefresh!: (response: Response) => void
  const refreshing = new Promise<Response>(resolve => { resolveRefresh = resolve })
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/certificates/11') { detailCalls++; return detailCalls === 1 ? json(detail) : refreshing }
    if (path === '/api/certificates/11/revoke') return json({ operation_id: 6, certificate_id: 11, status: 'REVOKED', changed })
    return json({ items: [item], page: 1, page_size: 20, total: 1 })
  }))
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ActorProvider><CertificatesPage /></ActorProvider></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: 'CERT-E-011' }))
  fireEvent.click(await screen.findByRole('button', { name: '撤销证书' }))
  fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
  await waitFor(() => expect(detailCalls).toBe(2))
  expect(screen.getByText(message)).toBeTruthy()
  resolveRefresh(json({ ...detail, status: 'REVOKED' }))
  await waitFor(() => expect(screen.getByText(message)).toBeTruthy())
  expect(screen.queryByRole('button', { name: '确认撤销' })).toBeNull()
})

it.each(['ACTIVE', 'REVOKED'] as const)('offers the saved revoke retry when a refreshed certificate is %s', async status => {
  const pending = createPendingWrite('alice@east.test', '/api/certificates/11/revoke', {})
  savePendingWrite(pending)
  const keys: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/certificates/11') return json({ ...detail, status })
    if (path === '/api/certificates/11/revoke') { keys.push(new Headers(options.headers).get('Idempotency-Key') ?? ''); return json({ operation_id: 6, certificate_id: 11, status: 'REVOKED', changed: true }) }
    return json({ items: [{ ...item, status }], page: 1, page_size: 20, total: 1 })
  }))
  render(<MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}><ActorProvider><CertificatesPage /></ActorProvider></MemoryRouter>)
  fireEvent.click(await screen.findByRole('button', { name: 'CERT-E-011' }))
  fireEvent.click(await screen.findByRole('button', { name: '继续未决撤销操作' }))
  fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
  expect(await screen.findByText('撤销成功')).toBeTruthy()
  expect(keys).toEqual([pending.key])
})
