import type { PendingWrite } from './pendingWrite'
import { clearPendingWrite, savePendingWrite } from './pendingWrite'
import { postJson } from '../api/client'

export async function submitWrite<T>(write: PendingWrite): Promise<T> {
  savePendingWrite(write)
  const result = await postJson<T>(write.path, write.actorEmail, write.key, write.body)
  clearPendingWrite(write)
  return result
}
