import { useEffect, useRef, useState } from 'react'
import { getJson } from '../api/client'
import type { BulkIssueResponse, Course, CoursesResponse, EnrollmentsResponse } from '../api/types'
import { useActor } from '../actor/ActorProvider'
import { createPendingWrite, loadPendingWrite, type PendingWrite } from '../lib/pendingWrite'
import { clearPendingWrite } from '../lib/pendingWrite'
import { submitWrite } from '../lib/writeRequest'
import { ApiError } from '../api/client'
import { BulkIssueResults } from './BulkIssueResults'

export function CoursesPage() {
  const { actorEmail, tenant, beginWrite, endWrite, writeInFlight } = useActor()
  const [courses, setCourses] = useState<Course[]>([])
  const [courseError, setCourseError] = useState<string | null>(null)
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [coursesRevision, setCoursesRevision] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [enrollments, setEnrollments] = useState<EnrollmentsResponse | null>(null)
  const [enrollmentsError, setEnrollmentsError] = useState<string | null>(null)
  const [enrollmentsLoading, setEnrollmentsLoading] = useState(false)
  const [enrollmentsRevision, setEnrollmentsRevision] = useState(0)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [write, setWrite] = useState<PendingWrite | null>(null)
  const [writeError, setWriteError] = useState<string | null>(null)
  const [conflict, setConflict] = useState(false)
  const [result, setResult] = useState<BulkIssueResponse | null>(null)
  const issueButtonRef = useRef<HTMLButtonElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)

  function closeConfirm() { setConfirmOpen(false); issueButtonRef.current?.focus() }
  useEffect(() => {
    if (!confirmOpen) return
    confirmButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy) closeConfirm() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [confirmOpen, busy])

  useEffect(() => {
    if (!tenant) { setCourses([]); setSelectedId(null); return }
    const controller = new AbortController()
    setCoursesLoading(true); setCourseError(null)
    getJson<CoursesResponse>('/api/courses', actorEmail, controller.signal).then(data => {
      if (controller.signal.aborted) return
      setCourses(data.items); setSelectedId(data.items[0]?.id ?? null); setCoursesLoading(false)
    }).catch(cause => {
      if (controller.signal.aborted) return
      setCourseError(cause instanceof Error ? cause.message : '加载课程失败'); setCoursesLoading(false)
    })
    return () => controller.abort()
  }, [actorEmail, tenant?.id, coursesRevision])

  useEffect(() => {
    if (!tenant || selectedId === null) { setEnrollments(null); return }
    const controller = new AbortController()
    setEnrollments(null); setEnrollmentsError(null); setEnrollmentsLoading(true)
    getJson<EnrollmentsResponse>(`/api/courses/${selectedId}/enrollments`, actorEmail, controller.signal).then(data => {
      if (!controller.signal.aborted) { setEnrollments(data); setEnrollmentsLoading(false) }
    }).catch(cause => {
      if (!controller.signal.aborted) { setEnrollmentsError(cause instanceof Error ? cause.message : '加载学员失败'); setEnrollmentsLoading(false) }
    })
    return () => controller.abort()
  }, [actorEmail, tenant?.id, selectedId, enrollmentsRevision])

  function selectCourse(id: number) {
    setSelectedId(id); setEnrollments(null); setResult(null); setWrite(null); setWriteError(null); setConflict(false); setConfirmOpen(false)
  }
  function discardConflict() {
    if (!conflict || busy) return
    const stale = write ?? loadPendingWrite(actorEmail, `/api/courses/${selectedId}/bulk-issue`)
    if (stale) clearPendingWrite(stale)
    setWrite(null); setWriteError(null); setConflict(false); closeConfirm()
  }
  async function issue() {
    if (selectedId === null) return
    const path = `/api/courses/${selectedId}/bulk-issue`
    const operation = write ?? loadPendingWrite(actorEmail, path) ?? createPendingWrite(actorEmail, path, {})
    if (!beginWrite(operation.key)) { setWriteError('该操作正在处理中'); return }
    setWrite(operation); setBusy(true); setWriteError(null); setConflict(false)
    try {
      const response = await submitWrite<BulkIssueResponse>(operation)
      setResult(response); closeConfirm(); setWrite(null)
      setEnrollmentsRevision(value => value + 1)
    } catch (cause) {
      setWriteError(cause instanceof Error ? cause.message : '请求结果不确定，请用原操作重试')
      setConflict(cause instanceof ApiError && cause.status === 409)
    } finally { setBusy(false); endWrite(operation.key) }
  }
  const rows = enrollments?.items ?? []
  const completed = rows.filter(row => row.status === 'COMPLETED').length
  const certified = rows.filter(row => row.active_certificate_id !== null).length
  const savedPending = selectedId === null ? null : loadPendingWrite(actorEmail, `/api/courses/${selectedId}/bulk-issue`)
  return <section>
    <div className="page-heading"><div><h1>课程完成情况</h1><p>{tenant?.name} · {tenant?.timezone}</p></div></div>
    {coursesLoading ? <p role="status">正在加载课程…</p> : courseError ? <div role="alert">{courseError} <button onClick={() => setCoursesRevision(value => value + 1)}>重试课程</button></div> : courses.length === 0 ? <p className="empty-state">暂无课程</p> : <>
      <label className="course-selector">课程<select value={selectedId ?? ''} disabled={busy} onChange={event => selectCourse(Number(event.target.value))}>{courses.map(course => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label>
      {enrollmentsLoading ? <p role="status">正在加载学员…</p> : enrollmentsError ? <div role="alert">{enrollmentsError} <button onClick={() => setEnrollmentsRevision(value => value + 1)}>重试学员</button></div> : enrollments && <>
        <div className="course-summary"><span>已完成 {completed}</span><span>未完成 {rows.length - completed}</span><span>已有有效证书 {certified}</span></div>
        {rows.length === 0 ? <p className="empty-state">该课程暂无学员</p> : <div className="table-scroll"><table><thead><tr><th>学员</th><th>完成状态</th><th>颁发资格</th></tr></thead><tbody>{rows.map(row => <tr key={row.learner_id}><td>{row.learner_name}</td><td>{row.status === 'COMPLETED' ? '已完成' : '未完成'}</td><td>{row.status === 'INCOMPLETE' ? '不可颁发' : row.active_certificate_id !== null ? '已有有效证书' : '可颁发'}</td></tr>)}</tbody></table></div>}
        <p className="muted">仅为已完成且当前无有效证书的学员颁发。</p><button ref={issueButtonRef} className="primary-button" type="button" disabled={busy || writeInFlight} onClick={() => { setWrite(savedPending); setConfirmOpen(true) }}>{savedPending ? '继续未决批量颁发操作' : '批量颁发'}</button>
      </>}
      {confirmOpen && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="批量颁发确认"><h2>批量颁发</h2><p>将为 {courses.find(course => course.id === selectedId)?.title} 中所有符合条件的学员颁发证书。</p>
        {writeError && <p role="alert">{writeError}</p>}<div className="modal-actions"><button type="button" disabled={busy} onClick={closeConfirm}>取消</button>{conflict && <button type="button" disabled={busy} onClick={discardConflict}>放弃冲突操作</button>}<button ref={confirmButtonRef} type="button" disabled={busy} onClick={issue}>{busy ? '处理中…' : writeError || savedPending ? '用同一操作重试' : '确认批量颁发'}</button></div>
      </div></div>}
      {result && <BulkIssueResults result={result} />}
    </>}
  </section>
}
