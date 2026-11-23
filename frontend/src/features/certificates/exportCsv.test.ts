import { afterEach, expect, it, vi } from 'vitest'
import { getJson } from '../../api/client'
import { exportCertificates } from './exportCsv'

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks() })

it('exports captured actor and filters without page while a list request can complete', async () => {
  let resolveExport!: (response: Response) => void
  const exportResponse = new Promise<Response>(resolve => { resolveExport = resolve })
  const requests: Array<{ path: string; email: string | null }> = []
  vi.stubGlobal('fetch', vi.fn(async (path: string, options: RequestInit) => {
    requests.push({ path, email: new Headers(options.headers).get('X-Actor-Email') })
    if (path.startsWith('/api/certificates/export?')) return exportResponse
    return new Response(JSON.stringify({ items: [], page: 1, page_size: 20, total: 0 }), { status: 200 })
  }))
  const createObjectURL = vi.fn(() => 'blob:csv')
  const revokeObjectURL = vi.fn()
  Object.defineProperty(URL, 'createObjectURL', { value: createObjectURL, configurable: true })
  Object.defineProperty(URL, 'revokeObjectURL', { value: revokeObjectURL, configurable: true })
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

  const exporting = exportCertificates('alice@east.test', { search: 'Alex Lee', sort: 'issued_local_date', direction: 'desc' }, 'East')
  const list = await getJson<{ total: number }>('/api/certificates?page=1', 'bob@west.test')
  expect(list.total).toBe(0)
  resolveExport(new Response('learner,course\nAlex Lee,Safety 101', { status: 200, headers: { 'Content-Type': 'text/csv' } }))
  await exporting
  expect(requests[0]).toEqual({ path: '/api/certificates/export?search=Alex+Lee&sort=issued_local_date&direction=desc', email: 'alice@east.test' })
  expect(requests[1].email).toBe('bob@west.test')
  expect(click).toHaveBeenCalledOnce()
  expect(createObjectURL).toHaveBeenCalledOnce()
  expect(revokeObjectURL).toHaveBeenCalledWith('blob:csv')
})
