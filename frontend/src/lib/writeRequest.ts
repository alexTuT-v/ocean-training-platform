import type { PendingWrite } from './pendingWrite'
import { clearPendingWrite, savePendingWrite } from './pendingWrite'
import { postJson } from '../api/client'

function validWriteResult(value: unknown, path: string): boolean {
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return false
  const result = value as Record<string, unknown>
  if (!Number.isSafeInteger(result.operation_id) || (result.operation_id as number) < 1) return false
  if (path.endsWith('/revoke') && result.status === 'REVOKED') return Number.isSafeInteger(result.certificate_id) && typeof result.changed === 'boolean'
  if (path.endsWith('/bulk-issue') && result.status === 'COMPLETED') return typeof result.summary === 'object' && result.summary !== null && Array.isArray(result.outcomes)
  return false
}

export async function submitWrite<T>(write: PendingWrite): Promise<T> {
  savePendingWrite(write)
  const result = await postJson<T>(write.path, write.actorEmail, write.key, write.body)
  if (!validWriteResult(result, write.path)) throw new Error('响应内容无效，请用原操作重试')
  clearPendingWrite(write)
  return result
}
