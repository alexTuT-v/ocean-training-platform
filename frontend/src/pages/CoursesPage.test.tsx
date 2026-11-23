import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { ActorProvider } from '../actor/ActorProvider'
import { CoursesPage } from './CoursesPage'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals() })
const me = { admin: { id: 1, email: 'alice@east.test' }, tenant: { id: 1, name: 'East', timezone: 'Australia/Sydney' } }
const courses = { items: [{ id: 1, title: 'Safety 101' }, { id: 2, title: 'First Aid' }] }
const enrollments = { course: courses.items[0], items: [{ learner_id: 1, learner_name: 'Alex Lee', status: 'COMPLETED', active_certificate_id: null }, { learner_id: 2, learner_name: 'Mia Chen', status: 'INCOMPLETE', active_certificate_id: null }] }
function json(body: unknown) { return new Response(JSON.stringify(body), { status: 200 }) }

it('clears the previous course learners when the selection changes', async () => {
  let resolveSecond!: (value: Response) => void
  const second = new Promise<Response>(resolve => { resolveSecond = resolve })
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path === '/api/courses/1/enrollments') return json(enrollments)
    if (path === '/api/courses/2/enrollments') return second
    throw new Error(path)
  }))
  render(<ActorProvider><CoursesPage /></ActorProvider>)
  expect(await screen.findByText('Alex Lee')).toBeTruthy()
  fireEvent.change(screen.getByRole('combobox', { name: '课程' }), { target: { value: '2' } })
  expect(screen.queryByText('Alex Lee')).toBeNull()
  resolveSecond(json({ course: courses.items[1], items: [] }))
  expect(await screen.findByText('该课程暂无学员')).toBeTruthy()
})

it('retries an uncertain bulk issue with one key and shows every learner outcome', async () => {
  const keys: string[] = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    if (path === '/api/me') return json(me)
    if (path === '/api/courses') return json(courses)
    if (path === '/api/courses/1/enrollments') return json(enrollments)
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
