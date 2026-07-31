export type User = {
  id: number
  email: string
  name: string
}

export type Workspace = {
  id: number
  name: string
  invite_code: string
  role: string
  created_at?: string
}

export type Member = {
  user_id: number
  name: string
  email: string
  role: string
}

export type KeyValue = {
  key: string
  value: string
  enabled: boolean
}

export type Collection = {
  id: number
  workspace_id: number
  name: string
}

export type ApiRequest = {
  id: number
  collection_id: number
  name: string
  method: string
  url: string
  headers: KeyValue[]
  params: KeyValue[]
  body_type: string
  body: string
  auth_type: string
  auth: Record<string, string>
  version: number
  updated_by?: number | null
  updated_at?: string | null
}

export type Environment = {
  id: number
  workspace_id: number
  name: string
  variables: KeyValue[]
  is_active: boolean
}

export type ProxyResponse = {
  status_code: number | null
  headers: Record<string, string>
  body: string
  duration_ms: number
  error?: string | null
}

export type OnlineUser = {
  user_id: number
  user_name: string
}
