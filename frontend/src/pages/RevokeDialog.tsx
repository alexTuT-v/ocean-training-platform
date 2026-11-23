import { useEffect, useRef, useState } from 'react'
import type { RevokeResponse } from '../api/types'
import { createPendingWrite, loadPendingWrite, type PendingWrite } from '../lib/pendingWrite'
import { clearPendingWrite } from '../lib/pendingWrite'
import { submitWrite } from '../lib/writeRequest'
import { ApiError } from '../api/client'

type Props = { id: number; serial: string; actorEmail: string; onDone: () => void; onClose: () => void; onBeginWrite?: (key: string) => boolean; onEndWrite?: (key: string) => void }

export function RevokeDialog({ id, serial, actorEmail, onDone, onClose, onBeginWrite, onEndWrite }: Props) {
  const path = `/api/certificates/${id}/revoke`
  const [write, setWrite] = useState<PendingWrite | null>(() => {
    return loadPendingWrite(actorEmail, path)
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [result, setResult] = useState<RevokeResponse | null>(null)
  const confirmRef = useRef<HTMLButtonElement>(null)
  useEffect(() => { confirmRef.current?.focus() }, [])
  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy) onClose() }
    document.addEventListener('keydown', closeOnEscape)
    return () => document.removeEventListener('keydown', closeOnEscape)
  }, [busy, onClose])

  async function confirm() {
    const operation = write ?? createPendingWrite(actorEmail, path, {})
    if (onBeginWrite && !onBeginWrite(operation.key)) { setError('该操作正在处理中'); return }
    setWrite(operation); setBusy(true); setError(null); setConflict(false)
    try {
      const response = await submitWrite<RevokeResponse>(operation)
      setResult(response)
      onDone()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '请求结果不确定，请用原操作重试')
      setConflict(cause instanceof ApiError && cause.status === 409)
    } finally { setBusy(false); onEndWrite?.(operation.key) }
  }

  function discardConflict() {
    if (!conflict || busy) return
    const stale = write ?? loadPendingWrite(actorEmail, path)
    if (stale) clearPendingWrite(stale)
    setWrite(null); setError(null); setConflict(false); onClose()
  }

  return <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="撤销证书确认">
    <h2>撤销证书</h2><p>请确认撤销以下证书：</p><strong>{serial}</strong>
    {result ? <p role="status">{result.changed ? '撤销成功' : '证书已撤销，无需重复操作'}</p> : <p>撤销后可再次颁发新证书，旧证书仍保留。</p>}
    {error && <p role="alert">{error}</p>}
    <div className="modal-actions"><button type="button" onClick={onClose} disabled={busy}>{result ? '关闭' : '取消'}</button>{!result && conflict && <button type="button" onClick={discardConflict} disabled={busy}>放弃冲突操作</button>}{!result && <button ref={confirmRef} type="button" onClick={confirm} disabled={busy}>{busy ? '处理中…' : error ? '用同一操作重试' : '确认撤销'}</button>}</div>
  </div></div>
}
