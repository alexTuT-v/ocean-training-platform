import { useEffect, useRef, useState } from 'react'
import { getJson } from '../api/client'
import type { CertificateDetail } from '../api/types'
import { useActor } from '../actor/ActorProvider'
import { RevokeDialog } from './RevokeDialog'
import { loadPendingWrite } from '../lib/pendingWrite'

export function CertificateDrawer({ id, actorEmail, onClose, onChanged }: { id: number; actorEmail: string; onClose: () => void; onChanged: () => void }) {
  const { beginWrite, endWrite, writeInFlight } = useActor()
  const [detail, setDetail] = useState<CertificateDetail | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showRevoke, setShowRevoke] = useState(false)
  const [revokeSerial, setRevokeSerial] = useState<string | null>(null)
  const [revision, setRevision] = useState(0)
  const revokeButtonRef = useRef<HTMLButtonElement>(null)
  const retryButtonRef = useRef<HTMLButtonElement>(null)
  const closeButtonRef = useRef<HTMLButtonElement>(null)
  function closeRevoke() { setShowRevoke(false); setRevokeSerial(null); (revokeButtonRef.current ?? retryButtonRef.current ?? closeButtonRef.current)?.focus() }
  const pendingRevoke = loadPendingWrite(actorEmail, `/api/certificates/${id}/revoke`)
  useEffect(() => { setShowRevoke(false); setRevokeSerial(null) }, [id, actorEmail])
  useEffect(() => {
    const controller = new AbortController()
    setDetail(null); setError(null)
    getJson<CertificateDetail>(`/api/certificates/${id}`, actorEmail, controller.signal).then(value => {
      if (!controller.signal.aborted) setDetail(value)
    }).catch(cause => { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : '加载详情失败') })
    return () => controller.abort()
  }, [id, actorEmail, revision])
  return <div className="drawer-backdrop" onClick={onClose}><aside className="drawer" aria-label="证书详情" onClick={event => event.stopPropagation()}>
    <div className="drawer-heading"><h2>证书详情</h2><button ref={closeButtonRef} type="button" onClick={onClose} aria-label="关闭详情">×</button></div>
    {error ? <p role="alert">{error}</p> : !detail ? <p role="status">正在加载详情…</p> : <><dl>
      <dt>序列号</dt><dd>{detail.serial_number}</dd><dt>学员</dt><dd>{detail.learner_name}</dd><dt>课程</dt><dd>{detail.course_title}</dd><dt>签发时间 · 租户本地</dt><dd>{detail.issued_local_datetime}</dd><dt>状态</dt><dd>{detail.status === 'ACTIVE' ? '有效' : '已撤销'}</dd>
    </dl>{pendingRevoke ? <button ref={retryButtonRef} type="button" className="primary-button" disabled={writeInFlight} onClick={() => { setRevokeSerial(detail.serial_number); setShowRevoke(true) }}>继续未决撤销操作</button> : detail.status === 'ACTIVE' && <button ref={revokeButtonRef} type="button" className="danger-button" disabled={writeInFlight} onClick={() => { setRevokeSerial(detail.serial_number); setShowRevoke(true) }}>撤销证书</button>}</>}
    {showRevoke && revokeSerial && <RevokeDialog id={id} serial={revokeSerial} actorEmail={actorEmail} onBeginWrite={beginWrite} onEndWrite={endWrite} onClose={closeRevoke} onDone={() => { setRevision(value => value + 1); onChanged() }} />}
  </aside></div>
}
