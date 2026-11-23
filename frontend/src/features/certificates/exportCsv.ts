export async function exportCertificates(actorEmail: string, filters: { search: string; sort: string; direction: 'asc' | 'desc' }, tenantName: string): Promise<void> {
  const query = new URLSearchParams({ search: filters.search, sort: filters.sort, direction: filters.direction })
  const response = await fetch(`/api/certificates/export?${query}`, { headers: { 'X-Actor-Email': actorEmail }, cache: 'no-store' })
  if (!response.ok) throw new Error(`导出失败（${response.status}）`)
  const objectUrl = URL.createObjectURL(await response.blob())
  const link = document.createElement('a')
  link.href = objectUrl
  link.download = `certificates-${tenantName.replace(/[^\p{L}\p{N}_-]/gu, '_')}.csv`
  document.body.append(link)
  try { link.click() } finally { link.remove(); URL.revokeObjectURL(objectUrl) }
}
