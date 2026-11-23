import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getJson } from '../api/client'
import type { CertificateListResponse } from '../api/types'
import { useActor } from '../actor/ActorProvider'
import { CertificateDrawer } from './CertificateDrawer'

const sortOptions = ['issued_local_date', 'learner_name', 'course_title', 'serial_number'] as const
type Sort = typeof sortOptions[number]

export function CertificatesPage() {
  const { actorEmail, tenant } = useActor()
  const [params, setParams] = useSearchParams()
  const [data, setData] = useState<CertificateListResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [revision, setRevision] = useState(0)
  const search = params.get('search') ?? ''
  const candidate = params.get('sort')
  const sort: Sort = sortOptions.includes(candidate as Sort) ? candidate as Sort : 'issued_local_date'
  const direction = params.get('direction') === 'asc' ? 'asc' : 'desc'
  const page = Math.max(1, Number(params.get('page')) || 1)

  useEffect(() => {
    if (!tenant) { setData(null); return }
    const controller = new AbortController()
    setLoading(true); setError(null)
    const query = new URLSearchParams({ search, sort, direction, page: String(page), page_size: '20' })
    getJson<CertificateListResponse>(`/api/certificates?${query}`, actorEmail, controller.signal).then(result => {
      if (!controller.signal.aborted) { setData(result); setLoading(false) }
    }).catch(cause => {
      if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : '加载证书失败'); setLoading(false) }
    })
    return () => controller.abort()
  }, [actorEmail, tenant?.id, search, sort, direction, page, revision])

  function updateParam(name: string, value: string, resetPage = false) {
    const next = new URLSearchParams(params)
    next.set(name, value)
    if (resetPage) next.set('page', '1')
    setParams(next)
  }
  return <section>
    <div className="page-heading"><div><h1>证书</h1><p>{tenant?.name} · {tenant?.timezone}</p></div><button type="button" disabled>导出 CSV</button></div>
    <div className="filters"><label>搜索学员或序列号<input type="search" value={search} onChange={event => updateParam('search', event.target.value, true)} /></label>
      <label>排序字段<select value={sort} onChange={event => updateParam('sort', event.target.value, true)}>{sortOptions.map(value => <option key={value} value={value}>{({ issued_local_date: '签发日期', learner_name: '学员', course_title: '课程', serial_number: '序列号' })[value]}</option>)}</select></label>
      <button type="button" onClick={() => updateParam('direction', direction === 'asc' ? 'desc' : 'asc', true)} aria-label="切换排序方向">{direction === 'asc' ? '升序 ↑' : '降序 ↓'}</button></div>
    {loading && <p role="status">正在加载证书…</p>}
    {!loading && error && <div role="alert">{error} <button type="button" onClick={() => setRevision(value => value + 1)}>重试列表</button></div>}
    {!loading && !error && data && (data.items.length === 0 ? <p className="empty-state">{search ? '没有匹配的证书' : '暂无证书'}</p> : <>
      <div className="table-scroll"><table><thead><tr><th>序列号</th><th>学员</th><th>课程</th><th>签发日期</th><th>状态</th></tr></thead><tbody>{data.items.map(item => <tr key={item.id}>
        <td><button type="button" className="text-button" onClick={() => setSelectedId(item.id)}>{item.serial_number}</button></td><td>{item.learner_name}</td><td>{item.course_title}</td><td>{item.issued_local_date}</td><td><span className={`status ${item.status.toLowerCase()}`}>{item.status === 'ACTIVE' ? '有效' : '已撤销'}</span></td>
      </tr>)}</tbody></table></div>
      <div className="pagination"><span>共 {data.total} 条 · 第 {page} 页</span><button type="button" disabled={page <= 1} onClick={() => updateParam('page', String(page - 1))}>上一页</button><button type="button" disabled={page * 20 >= data.total} onClick={() => updateParam('page', String(page + 1))}>下一页</button></div>
    </>)}
    {selectedId !== null && <CertificateDrawer id={selectedId} actorEmail={actorEmail} onClose={() => setSelectedId(null)} />}
  </section>
}
