import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { ActorProvider } from '../actor/ActorProvider'
import { CertificatesPage } from './CertificatesPage'

afterEach(() => { cleanup(); vi.unstubAllGlobals() })
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
