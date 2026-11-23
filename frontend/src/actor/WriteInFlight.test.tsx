import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import App from '../App'

afterEach(() => { cleanup(); sessionStorage.clear(); vi.unstubAllGlobals(); window.history.replaceState({}, '', '/') })
function json(body: unknown) { return new Response(JSON.stringify(body), { status: 200 }) }

it('keeps a bulk write locked across route navigation until its POST finishes', async () => {
  window.history.replaceState({}, '', '/courses')
  let resolvePost!: (response: Response) => void
  const post = new Promise<Response>(resolve => { resolvePost = resolve })
  let postCalls = 0
  vi.stubGlobal('fetch', vi.fn(async (path: string) => {
    if (path === '/api/me') return json({ admin: { id: 1, email: 'alice@east.test' }, tenant: { id: 1, name: 'East', timezone: 'Australia/Sydney' } })
    if (path === '/api/courses') return json({ items: [{ id: 1, title: 'Safety 101' }] })
    if (path.startsWith('/api/courses/1/enrollments?')) return json({ course: { id: 1, title: 'Safety 101' }, page: 1, page_size: 20, total: 1, summary: { completed: 1, incomplete: 0, active_certificates: 0 }, items: [{ learner_id: 1, learner_name: 'Alex Lee', status: 'COMPLETED', active_certificate_id: null }] })
    if (path === '/api/courses/1/bulk-issue') { postCalls++; return post }
    if (path.startsWith('/api/certificates?')) return json({ items: [], page: 1, page_size: 20, total: 0 })
    throw new Error(path)
  }))
  render(<App />)
  expect(await screen.findByText('Alex Lee')).toBeTruthy()
  fireEvent.click(screen.getByRole('checkbox', { name: '选择 Alex Lee' }))
  fireEvent.click(screen.getByRole('button', { name: '批量颁发' }))
  fireEvent.click(screen.getByRole('button', { name: '确认批量颁发' }))
  await waitFor(() => expect(postCalls).toBe(1))
  fireEvent.click(screen.getByRole('link', { name: '证书' }))
  fireEvent.click(screen.getByRole('link', { name: '课程完成' }))
  const issue = await screen.findByRole('button', { name: '继续未决批量颁发操作' })
  expect(issue.hasAttribute('disabled')).toBe(true)
  expect(screen.getByRole('button', { name: /Alice · East/ }).hasAttribute('disabled')).toBe(true)
  resolvePost(json({ operation_id: 5, status: 'COMPLETED', summary: { issued: 1, skipped: 0, failed: 0 }, outcomes: [] }))
  await waitFor(() => expect(screen.getByRole('button', { name: /Alice · East/ }).hasAttribute('disabled')).toBe(false))
  expect(issue.hasAttribute('disabled')).toBe(true)
  expect(screen.getByRole('checkbox', { name: '选择 Alex Lee' }).hasAttribute('disabled')).toBe(false)
  expect(postCalls).toBe(1)
})
