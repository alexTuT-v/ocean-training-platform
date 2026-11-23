export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); this.name = 'ApiError' }
}

async function parseJson<T>(response: Response): Promise<T> {
  let body: unknown
  try { body = await response.json() } catch {
    if (response.ok) throw new Error('响应内容无法读取，请用原操作重试')
    body = null
  }
  if (!response.ok) {
    const message = typeof body === 'object' && body !== null && 'message' in body && typeof body.message === 'string' ? body.message : `请求失败（${response.status}）`
    throw new ApiError(response.status, message)
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) throw new Error('响应内容无效，请用原操作重试')
  return body as T
}

export async function getJson<T>(path: string, actorEmail: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { headers: { 'X-Actor-Email': actorEmail }, cache: 'no-store', signal })
  return parseJson<T>(response)
}

export async function postJson<T>(path: string, actorEmail: string, key: string, body: object = {}): Promise<T> {
  const response = await fetch(path, { method: 'POST', headers: { 'X-Actor-Email': actorEmail, 'Idempotency-Key': key, 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  return parseJson<T>(response)
}
