import { useEffect, useRef, useState } from 'react'
import { getJson } from '../api/client'
import type { BulkIssueResponse, Course, CoursesResponse, EnrollmentsResponse } from '../api/types'
import { useActor } from '../actor/ActorProvider'
import { createPendingWrite, loadPendingWrite, type PendingWrite } from '../lib/pendingWrite'
import { clearPendingWrite } from '../lib/pendingWrite'
import { submitWrite } from '../lib/writeRequest'
import { ApiError } from '../api/client'
import { BulkIssueResults } from './BulkIssueResults'
import { CertificateDrawer } from './CertificateDrawer'

export function CoursesPage() {
  const { actorEmail, tenant, beginWrite, endWrite, writeInFlight } = useActor()
  const [courses, setCourses] = useState<Course[]>([])
  const [courseError, setCourseError] = useState<string | null>(null)
  const [coursesLoading, setCoursesLoading] = useState(true)
  const [coursesRevision, setCoursesRevision] = useState(0)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [selectedCertificateId, setSelectedCertificateId] = useState<number | null>(null)
  const [selectedLearnerIds, setSelectedLearnerIds] = useState<Set<number>>(new Set())
  const [confirmationIds, setConfirmationIds] = useState<number[]>([])
  const [page, setPage] = useState(1)
  const [enrollments, setEnrollments] = useState<EnrollmentsResponse | null>(null)
  const [enrollmentsError, setEnrollmentsError] = useState<string | null>(null)
  const [enrollmentsLoading, setEnrollmentsLoading] = useState(false)
  const [enrollmentsRevision, setEnrollmentsRevision] = useState(0)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [write, setWrite] = useState<PendingWrite | null>(null)
  const [writeError, setWriteError] = useState<string | null>(null)
  const [discardable, setDiscardable] = useState(false)
  const [result, setResult] = useState<BulkIssueResponse | null>(null)
  const issueButtonRef = useRef<HTMLButtonElement>(null)
  const confirmButtonRef = useRef<HTMLButtonElement>(null)

  function closeConfirm() { setConfirmOpen(false); setConfirmationIds([]); issueButtonRef.current?.focus() }
  useEffect(() => { setSelectedLearnerIds(new Set()); setConfirmationIds([]) }, [actorEmail])
  useEffect(() => {
    if (!confirmOpen) return
    confirmButtonRef.current?.focus()
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape' && !busy) closeConfirm() }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [confirmOpen, busy])

  useEffect(() => {
    if (!tenant) { setCourses([]); setSelectedId(null); setSelectedCertificateId(null); setSelectedLearnerIds(new Set()); setPage(1); return }
    const controller = new AbortController()
    setCoursesLoading(true); setCourseError(null)
    getJson<CoursesResponse>('/api/courses', actorEmail, controller.signal).then(data => {
      if (controller.signal.aborted) return
      setCourses(data.items); setSelectedId(data.items[0]?.id ?? null); setSelectedCertificateId(null); setPage(1); setCoursesLoading(false)
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
    getJson<EnrollmentsResponse>(`/api/courses/${selectedId}/enrollments?page=${page}&page_size=20`, actorEmail, controller.signal).then(data => {
      if (!controller.signal.aborted) { setEnrollments(data); setEnrollmentsLoading(false) }
    }).catch(cause => {
      if (!controller.signal.aborted) { setEnrollmentsError(cause instanceof Error ? cause.message : '加载学员失败'); setEnrollmentsLoading(false) }
    })
    return () => controller.abort()
  }, [actorEmail, tenant?.id, selectedId, page, enrollmentsRevision])

  function selectCourse(id: number) {
    setSelectedId(id); setSelectedCertificateId(null); setSelectedLearnerIds(new Set()); setConfirmationIds([]); setPage(1); setEnrollments(null); setResult(null); setWrite(null); setWriteError(null); setDiscardable(false); setConfirmOpen(false)
  }
  function toggleLearner(id: number, checked: boolean) {
    setSelectedLearnerIds(current => {
      const next = new Set(current)
      if (checked) next.add(id)
      else next.delete(id)
      return next
    })
  }
  function togglePage(ids: number[], checked: boolean) {
    setSelectedLearnerIds(current => {
      const next = new Set(current)
      for (const id of ids) {
        if (checked) next.add(id)
        else next.delete(id)
      }
      return next
    })
  }
  function discardPending() {
    if (!discardable || busy) return
    const stale = write ?? loadPendingWrite(actorEmail, `/api/courses/${selectedId}/bulk-issue`)
    if (stale) clearPendingWrite(stale)
    setWrite(null); setWriteError(null); setDiscardable(false); closeConfirm()
  }
  async function issue() {
    if (selectedId === null) return
    const path = `/api/courses/${selectedId}/bulk-issue`
    const operation = write ?? loadPendingWrite(actorEmail, path) ?? createPendingWrite(actorEmail, path, { learner_ids: confirmationIds })
    if (!beginWrite(operation.key)) { setWriteError('该操作正在处理中'); return }
    setWrite(operation); setBusy(true); setWriteError(null); setDiscardable(false)
    try {
      const response = await submitWrite<BulkIssueResponse>(operation)
      setResult(response); closeConfirm(); setWrite(null); setSelectedLearnerIds(new Set())
      setEnrollmentsRevision(value => value + 1)
    } catch (cause) {
      setWriteError(cause instanceof Error ? cause.message : '请求结果不确定，请用原操作重试')
      setDiscardable(cause instanceof ApiError && (cause.status === 409 || cause.status === 422))
    } finally { setBusy(false); endWrite(operation.key) }
  }
  const rows = enrollments?.items ?? []
  const visibleEligibleIds = rows.filter(row => row.status === 'COMPLETED' && row.active_certificate_id === null).map(row => row.learner_id)
  const selectedOnPage = visibleEligibleIds.filter(id => selectedLearnerIds.has(id)).length
  const totalPages = enrollments ? Math.max(1, Math.ceil(enrollments.total / enrollments.page_size)) : 1
  const savedPending = selectedId === null ? null : loadPendingWrite(actorEmail, `/api/courses/${selectedId}/bulk-issue`)
  const selectionLocked = busy || writeInFlight || savedPending !== null
  const pendingIds = savedPending ? (savedPending.body as { learner_ids?: unknown }).learner_ids : null
  const pendingCount = Array.isArray(pendingIds) ? pendingIds.length : null
  return <section>
    <div className="page-heading"><div><h1>课程完成情况</h1><p>{tenant?.name} · {tenant?.timezone}</p></div></div>
    {coursesLoading ? <p role="status">正在加载课程…</p> : courseError ? <div role="alert">{courseError} <button onClick={() => setCoursesRevision(value => value + 1)}>重试课程</button></div> : courses.length === 0 ? <p className="empty-state">暂无课程</p> : <>
      <label className="course-selector">课程<select value={selectedId ?? ''} disabled={busy} onChange={event => selectCourse(Number(event.target.value))}>{courses.map(course => <option key={course.id} value={course.id}>{course.title}</option>)}</select></label>
      {enrollmentsLoading ? <p role="status">正在加载学员…</p> : enrollmentsError ? <div role="alert">{enrollmentsError} <button onClick={() => setEnrollmentsRevision(value => value + 1)}>重试学员</button></div> : enrollments && <>
        <div className="course-summary"><span>已完成 {enrollments.summary.completed}</span><span>未完成 {enrollments.summary.incomplete}</span><span>已有有效证书 {enrollments.summary.active_certificates}</span></div>
        {rows.length === 0 ? <p className="empty-state">{enrollments.total === 0 ? '该课程暂无学员' : '当前页无学员'}</p> : <div className="table-scroll"><table><thead><tr><th><label><input type="checkbox" aria-label="全选当前页可颁发学员" checked={visibleEligibleIds.length > 0 && selectedOnPage === visibleEligibleIds.length} ref={input => { if (input) input.indeterminate = selectedOnPage > 0 && selectedOnPage < visibleEligibleIds.length }} disabled={selectionLocked || visibleEligibleIds.length === 0} onChange={event => togglePage(visibleEligibleIds, event.target.checked)} /> 全选本页</label></th><th>学员</th><th>完成状态</th><th>颁发资格</th></tr></thead><tbody>{rows.map(row => {
          const eligible = row.status === 'COMPLETED' && row.active_certificate_id === null
          return <tr key={row.learner_id}><td><input type="checkbox" aria-label={`选择 ${row.learner_name}`} checked={selectedLearnerIds.has(row.learner_id)} disabled={selectionLocked || !eligible} onChange={event => toggleLearner(row.learner_id, event.target.checked)} /></td><td>{row.learner_name}</td><td>{row.status === 'COMPLETED' ? '已完成' : '未完成'}</td><td>{row.status === 'INCOMPLETE' ? '不可颁发' : row.active_certificate_id !== null ? <button type="button" className="text-button" onClick={() => setSelectedCertificateId(row.active_certificate_id)}>查看并撤销证书</button> : '可颁发'}</td></tr>
        })}</tbody></table></div>}
        {enrollments.total > 0 && <div className="pagination"><span>共 {enrollments.total} 名学员 · 第 {enrollments.page} / {totalPages} 页</span><button type="button" disabled={page <= 1} onClick={() => setPage(value => value - 1)}>上一页</button><button type="button" disabled={page >= totalPages} onClick={() => setPage(value => value + 1)}>下一页</button></div>}
        <p className="muted">仅可选择已完成且当前无有效证书的学员。全选仅作用于当前页。</p><div className="selection-actions"><span role="status">已选 {selectedLearnerIds.size} 名学员</span><button ref={issueButtonRef} className="primary-button" type="button" disabled={busy || writeInFlight || (!savedPending && selectedLearnerIds.size === 0)} onClick={() => { setWrite(savedPending); setConfirmationIds(savedPending && Array.isArray(pendingIds) ? pendingIds as number[] : [...selectedLearnerIds].sort((a, b) => a - b)); setWriteError(null); setDiscardable(false); setResult(null); setConfirmOpen(true) }}>{savedPending ? '继续未决批量颁发操作' : '批量颁发'}</button></div>
      </>}
      {confirmOpen && <div className="modal-backdrop"><div className="modal" role="dialog" aria-modal="true" aria-label="批量颁发确认"><h2>批量颁发</h2><p>{savedPending ? pendingCount === null ? '继续上次已选学员的颁发请求，沿用原选择和操作键。' : `继续上次为 ${pendingCount} 名学员提交的请求，沿用原选择和操作键。` : `将为 ${courses.find(course => course.id === selectedId)?.title} 中已选的 ${confirmationIds.length} 名学员颁发证书。`}</p>
        {writeError && <p role="alert">{writeError}</p>}<div className="modal-actions"><button type="button" disabled={busy} onClick={closeConfirm}>取消</button>{discardable && <button type="button" disabled={busy} onClick={discardPending}>放弃未决操作</button>}<button ref={confirmButtonRef} type="button" disabled={busy} onClick={issue}>{busy ? '处理中…' : writeError || savedPending ? '用同一操作重试' : '确认批量颁发'}</button></div>
      </div></div>}
      {result && <BulkIssueResults result={result} />}
    </>}
    {selectedCertificateId !== null && <CertificateDrawer id={selectedCertificateId} actorEmail={actorEmail} onClose={() => setSelectedCertificateId(null)} onChanged={() => setEnrollmentsRevision(value => value + 1)} />}
  </section>
}
