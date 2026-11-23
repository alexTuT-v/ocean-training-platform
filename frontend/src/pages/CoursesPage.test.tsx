import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ActorProvider } from '../actor/ActorProvider'
import { CoursesPage } from './CoursesPage'
import { createPendingWrite, loadPendingWrite, savePendingWrite } from '../lib/pendingWrite'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })
const me = { admin: { id: 1, email: 'alice@east.test' }, tenant: { id: 1, name: 'East', timezone: 'Australia/Sydney' } }
const courses = { items: [{ id: 1, title: 'Safety 101' }, { id: 2, title: 'First Aid' }] }
const enrollments = { course: courses.items[0], page: 1, page_size: 20, total: 2, summary: { completed: 1, incomplete: 1, active_certificates: 0 }, items: [{ learner_id: 1, learner_name: 'Alex Lee', status: 'COMPLETED', active_certificate_id: null }, { learner_id: 2, learner_name: 'Mia Chen', status: 'INCOMPLETE', active_certificate_id: null }] }
function json(body: unknown) { return new Response(JSON.stringify(body), { status: 200 }) }

it('clears the previous course learners when the selection changes', async () => {
  let resolveSecond!: (value: Response) => void
  const second = new Promise<Response>(resolve => { resolveSecond = resolve })
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path.startsWith('/api/courses/1/enrollments?')) return json(enrollments)
    if (path.startsWith('/api/courses/2/enrollments?')) return second
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  expect(await screen.findByText('Alex Lee')).toBeTruthy()
  fireEvent.change(screen.getByRole('combobox', { name: '课程' }), { target: { value: '2' } })
  expect(screen.queryByText('Alex Lee')).toBeNull()
  resolveSecond(json({ course: courses.items[1], page: 1, page_size: 20, total: 0, summary: { completed: 0, incomplete: 0, active_certificates: 0 }, items: [] }))
  expect(await screen.findByText('该课程暂无学员')).toBeTruthy()
})

it('shows only the requested enrollment page and keeps whole-course totals', async () => {
  const paths: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    paths.push(path)
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path.startsWith('/api/courses/1/enrollments?')) {
      const page = Number(new URL(path, 'http://local').searchParams.get('page'))
      return json({ course: courses.items[0], page, page_size: 20, total: 21, summary: { completed: 20, incomplete: 1, active_certificates: 3 }, items: page === 1 ? [enrollments.items[0]] : [{ learner_id: 21, learner_name: 'Last Learner', status: 'INCOMPLETE', active_certificate_id: null }] })
    }
    if (path.startsWith('/api/courses/2/enrollments?')) return json({ course: courses.items[1], page: 1, page_size: 20, total: 0, summary: { completed: 0, incomplete: 0, active_certificates: 0 }, items: [] })
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  expect(await screen.findByText('Alex Lee')).toBeTruthy()
  expect(screen.getByText('已完成 20')).toBeTruthy()
  expect(screen.getByText('共 21 名学员 · 第 1 / 2 页')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '下一页' }))
  expect(await screen.findByText('Last Learner')).toBeTruthy()
  expect(screen.queryByText('Alex Lee')).toBeNull()
  expect(screen.getByText('已完成 20')).toBeTruthy()
  expect(paths).toContain('/api/courses/1/enrollments?page=2&page_size=20')
  fireEvent.change(screen.getByRole('combobox', { name: '课程' }), { target: { value: '2' } })
  expect(await screen.findByText('该课程暂无学员')).toBeTruthy()
  expect(paths).toContain('/api/courses/2/enrollments?page=1&page_size=20')
})

it('opens an active course certificate for revocation and refreshes its eligibility', async () => {
  let revoked = false
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path.startsWith('/api/courses/1/enrollments?')) return json({ ...enrollments, summary: { completed: 1, incomplete: 1, active_certificates: revoked ? 0 : 1 }, items: [{ ...enrollments.items[0], active_certificate_id: revoked ? null : 11 }, enrollments.items[1]] })
    if (path === '/api/certificates/11') return json({ id: 11, serial_number: 'CERT-E-011', learner_name: 'Alex Lee', course_title: 'Safety 101', issued_local_date: '2026-01-11', issued_local_datetime: '2026-01-11 00:30', status: revoked ? 'REVOKED' : 'ACTIVE' })
    if (path === '/api/certificates/11/revoke') { revoked = true; return json({ operation_id: 8, certificate_id: 11, status: 'REVOKED', changed: true }) }
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  fireEvent.click(await screen.findByRole('button', { name: '查看并撤销证书' }))
  expect(await screen.findByText('CERT-E-011')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '撤销证书' }))
  fireEvent.click(screen.getByRole('button', { name: '确认撤销' }))
  expect(await screen.findByText('撤销成功')).toBeTruthy()
  await waitFor(() => expect(screen.getByText('已有有效证书 0')).toBeTruthy())
})

it('retries an uncertain bulk issue with one key and shows every learner outcome', async () => {
  const keys: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path.startsWith('/api/courses/1/enrollments?')) return json(enrollments)
    if (path.endsWith('/bulk-issue')) {
      keys.push(new Headers(options.headers).get('Idempotency-Key') ?? '')
      if (keys.length === 1) throw new Error('network timeout')
      return json({ operation_id: 5, status: 'COMPLETED', summary: { issued: 1, skipped: 1, failed: 1 }, outcomes: [
        { learner_id: 1, learner_name: 'Alex Lee', result: 'issued', reason: null, certificate_id: 30, serial_number: 'CERT-E-030' },
        { learner_id: 2, learner_name: 'Mia Chen', result: 'skipped', reason: '未完成课程', certificate_id: null, serial_number: null },
        { learner_id: 3, learner_name: 'Sam Wu', result: 'failed', reason: '数据错误', certificate_id: null, serial_number: null },
      ] })
    }
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  expect(await screen.findByText('Alex Lee')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '批量颁发' }))
  expect(keys).toHaveLength(0)
  fireEvent.click(screen.getByRole('button', { name: '确认批量颁发' }))
  expect(await screen.findByText('network timeout')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '用同一操作重试' }))
  expect(await screen.findByText('CERT-E-030')).toBeTruthy()
  expect(screen.getByText('未完成课程')).toBeTruthy()
  expect(screen.getByText('数据错误')).toBeTruthy()
  expect(keys).toHaveLength(2)
  expect(keys[0]).toBe(keys[1])
})

it('shows a recoverable course load error', async () => {
  let calls = 0
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') { calls++; if (calls === 1) throw new Error('load failed'); return json({ items: [] }) }
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  expect(await screen.findByRole('alert')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '重试课程' }))
  await waitFor(() => expect(screen.getByText('暂无课程')).toBeTruthy())
})

it('focuses bulk confirmation and returns focus when Escape closes it', async () => {
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    return json(enrollments)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  expect(await screen.findByText('Alex Lee')).toBeTruthy()
  const trigger = screen.getByRole('button', { name: '批量颁发' })
  fireEvent.click(trigger)
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '确认批量颁发' }))
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(screen.queryByRole('dialog')).toBeNull()
  expect(document.activeElement).toBe(trigger)
})

it('offers an explicit retry for a saved bulk issue after page refresh', async () => {
  const pending = createPendingWrite('alice@east.test', '/api/courses/1/bulk-issue', {})
  savePendingWrite(pending)
  const keys: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path.startsWith('/api/courses/1/enrollments?')) return json(enrollments)
    if (path.endsWith('/bulk-issue')) { keys.push(new Headers(options.headers).get('Idempotency-Key') ?? ''); return json({ operation_id: 5, status: 'COMPLETED', summary: { issued: 0, skipped: 0, failed: 0 }, outcomes: [] }) }
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  const retry = await screen.findByRole('button', { name: '继续未决批量颁发操作' })
  fireEvent.click(retry)
  fireEvent.click(screen.getByRole('button', { name: '用同一操作重试' }))
  await waitFor(() => expect(keys).toEqual([pending.key]))
})

it('lets an administrator discard a confirmed key conflict and begin a fresh bulk issue', async () => {
  const other = createPendingWrite('bob@west.test', '/api/courses/2/bulk-issue', {})
  savePendingWrite(other)
  const keys: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path.startsWith('/api/courses/1/enrollments?')) return json(enrollments)
    if (path.endsWith('/bulk-issue')) {
      keys.push(new Headers(options.headers).get('Idempotency-Key') ?? '')
      if (keys.length === 1) return new Response(JSON.stringify({ code: 'IDEMPOTENCY_CONFLICT', message: 'key conflict' }), { status: 409 })
      return json({ operation_id: 5, status: 'COMPLETED', summary: { issued: 0, skipped: 0, failed: 0 }, outcomes: [] })
    }
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  fireEvent.click(await screen.findByRole('button', { name: '批量颁发' }))
  fireEvent.click(screen.getByRole('button', { name: '确认批量颁发' }))
  expect(await screen.findByText('key conflict')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: '放弃冲突操作' }))
  expect(loadPendingWrite('alice@east.test', '/api/courses/1/bulk-issue')).toBeNull()
  expect(loadPendingWrite('bob@west.test', '/api/courses/2/bulk-issue')?.key).toBe(other.key)
  fireEvent.click(screen.getByRole('button', { name: '批量颁发' }))
  fireEvent.click(screen.getByRole('button', { name: '确认批量颁发' }))
  expect(await screen.findByText('操作已完成')).toBeTruthy()
  expect(keys).toHaveLength(2)
  expect(keys[1]).not.toBe(keys[0])
})
