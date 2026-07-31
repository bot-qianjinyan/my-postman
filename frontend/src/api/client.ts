import type {
  ApiRequest,
  Collection,
  Environment,
  KeyValue,
  Member,
  ProxyResponse,
  User,
  Workspace,
} from './types'

const TOKEN_KEY = 'mypostman_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json')
  }
  const token = getToken()
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const res = await fetch(path, { ...options, headers })
  if (!res.ok) {
    let detail: unknown = await res.text()
    try {
      detail = JSON.parse(detail as string)
    } catch {
      /* keep text */
    }
    const err = new Error('Request failed') as Error & { status: number; detail: unknown }
    err.status = res.status
    err.detail = detail
    throw err
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  register(body: { email: string; name: string; password: string }) {
    return request<{ access_token: string; user: User }>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
  login(body: { email: string; password: string }) {
    return request<{ access_token: string; user: User }>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
  me() {
    return request<User>('/api/auth/me')
  },
  listWorkspaces() {
    return request<Workspace[]>('/api/workspaces')
  },
  createWorkspace(name: string) {
    return request<Workspace>('/api/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  },
  joinWorkspace(invite_code: string) {
    return request<Workspace>('/api/workspaces/join', {
      method: 'POST',
      body: JSON.stringify({ invite_code }),
    })
  },
  listMembers(workspaceId: number) {
    return request<Member[]>(`/api/workspaces/${workspaceId}/members`)
  },
  listCollections(workspaceId: number) {
    return request<Collection[]>(`/api/workspaces/${workspaceId}/collections`)
  },
  createCollection(workspaceId: number, name: string) {
    return request<Collection>(`/api/workspaces/${workspaceId}/collections`, {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  },
  listRequests(collectionId: number) {
    return request<ApiRequest[]>(`/api/collections/${collectionId}/requests`)
  },
  createRequest(collectionId: number, body: { name: string; method?: string; url?: string }) {
    return request<ApiRequest>(`/api/collections/${collectionId}/requests`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
  updateRequest(requestId: number, body: Partial<ApiRequest> & { version?: number }) {
    return request<ApiRequest>(`/api/requests/${requestId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
  },
  deleteRequest(requestId: number) {
    return request<{ ok: boolean }>(`/api/requests/${requestId}`, { method: 'DELETE' })
  },
  listEnvironments(workspaceId: number) {
    return request<Environment[]>(`/api/workspaces/${workspaceId}/environments`)
  },
  updateEnvironment(
    environmentId: number,
    body: { name?: string; variables?: KeyValue[]; is_active?: boolean },
  ) {
    return request<Environment>(`/api/environments/${environmentId}`, {
      method: 'PUT',
      body: JSON.stringify(body),
    })
  },
  sendProxy(body: {
    workspace_id: number
    request_id?: number | null
    method: string
    url: string
    headers: KeyValue[]
    params: KeyValue[]
    body?: string | null
    body_type: string
  }) {
    return request<ProxyResponse>('/api/proxy/send', {
      method: 'POST',
      body: JSON.stringify(body),
    })
  },
}
