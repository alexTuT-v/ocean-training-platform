import { afterEach, expect, it, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { RevokeDialog } from './RevokeDialog'

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
