import type { BulkIssueResponse } from '../api/types'

export function BulkIssueResults({ result }: { result: BulkIssueResponse }) {
  return <section className="result-panel" aria-label="批量颁发结果"><h2>操作已完成</h2><p>已颁发 {result.summary.issued} · 已跳过 {result.summary.skipped} · 失败 {result.summary.failed}</p>
    <div className="table-scroll"><table><thead><tr><th>学员</th><th>结果</th><th>原因 / 序列号</th></tr></thead><tbody>{result.outcomes.map(outcome => <tr key={outcome.learner_id}><td>{outcome.learner_name}</td><td>{outcome.result === 'issued' ? '已颁发' : outcome.result === 'skipped' ? '已跳过' : '失败'}</td><td>{outcome.serial_number ?? outcome.reason ?? '—'}</td></tr>)}</tbody></table></div>
  </section>
}
