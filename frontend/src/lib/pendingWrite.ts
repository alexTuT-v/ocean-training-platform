export type PendingWrite = { actorEmail: string; method: 'POST'; path: string; body: object; key: string; createdAt: number }
const storageKey = 'ocean-pending-write'
export function createPendingWrite(actorEmail: string, path: string, body: object): PendingWrite { return { actorEmail, method: 'POST', path, body, key: crypto.randomUUID(), createdAt: Date.now() } }
function readPending(): PendingWrite[] {
  const raw = sessionStorage.getItem(storageKey)
  if (!raw) return []
  try {
    const values = JSON.parse(raw) as unknown
    return Array.isArray(values) ? values.filter((value): value is PendingWrite => value?.method === 'POST' && typeof value.key === 'string' && typeof value.path === 'string') : []
  } catch { return [] }
}
export function loadPendingWrite(actorEmail?: string, path?: string): PendingWrite | null {
  return readPending().filter(value => (!actorEmail || value.actorEmail === actorEmail) && (!path || value.path === path)).at(-1) ?? null
}
export function savePendingWrite(write: PendingWrite): void {
  const values = readPending().filter(value => value.key !== write.key)
  values.push(write)
  sessionStorage.setItem(storageKey, JSON.stringify(values))
}
export function clearPendingWrite(write?: PendingWrite): void {
  if (!write) { sessionStorage.removeItem(storageKey); return }
  sessionStorage.setItem(storageKey, JSON.stringify(readPending().filter(value => value.key !== write.key)))
}
