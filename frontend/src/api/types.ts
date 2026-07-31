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
  description?: string
}

export type ApiRequest = {
  id: number
  collection_id: number
  name: string
  description?: string
  protocol: string
  method: string
  url: string
  headers: KeyValue[]
  params: KeyValue[]
  body_type: string
  body: string
  auth_type: string
  auth: Record<string, string>
  pre_request_script: string
  test_script: string
  graphql_query: string
  graphql_variables: string
  grpc_service: string
  grpc_method: string
  grpc_message: string
  ws_messages: string[]
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

export type AssertionResult = {
  name: string
  passed: boolean
  error?: string | null
}

export type ProxyResponse = {
  status_code: number | null
  headers: Record<string, string>
  body: string
  duration_ms: number
  error?: string | null
  assertions?: AssertionResult[]
  env_updates?: KeyValue[]
}

export type RunnerResult = {
  run_id: number
  status: string
  total: number
  passed: number
  failed: number
  items: Array<{
    request_id: number
    name: string
    status_code: number | null
    duration_ms: number
    error?: string | null
    assertions: AssertionResult[]
    passed: boolean
  }>
}

export type MockServer = {
  id: number
  workspace_id: number
  name: string
  slug: string
  is_enabled: boolean
  base_url: string
  routes: Array<{
    id: number
    method: string
    path: string
    status_code: number
    headers: Record<string, string>
    body: string
    delay_ms: number
  }>
}

export type Comment = {
  id: number
  workspace_id: number
  request_id: number | null
  user_id: number
  user_name: string
  body: string
  mentions: number[]
  created_at?: string
}

export type Monitor = {
  id: number
  workspace_id: number
  collection_id: number
  environment_id: number | null
  name: string
  interval_minutes: number
  is_enabled: boolean
  last_run_at: string | null
  last_status: string
  last_summary: string
}

export type Docs = {
  workspace_id: number
  title: string
  markdown: string
  html: string
}

export type OnlineUser = {
  user_id: number
  user_name: string
}
