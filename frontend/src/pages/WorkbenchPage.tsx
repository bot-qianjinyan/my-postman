import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type {
  ApiRequest,
  Collection,
  Environment,
  KeyValue,
  Member,
  ProxyResponse,
} from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useWorkspaceSocket } from '../hooks/useWorkspaceSocket'
import { interpolate } from '../utils/env'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']

function emptyKV(): KeyValue[] {
  return [{ key: '', value: '', enabled: true }]
}

export function WorkbenchPage() {
  const { workspaceId } = useParams()
  const wid = Number(workspaceId)
  const { user, logout } = useAuth()

  const [workspaceName, setWorkspaceName] = useState('Workspace')
  const [inviteCode, setInviteCode] = useState('')
  const [members, setMembers] = useState<Member[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [requests, setRequests] = useState<ApiRequest[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [activeReqId, setActiveReqId] = useState<number | null>(null)
  const [draft, setDraft] = useState<ApiRequest | null>(null)
  const [tab, setTab] = useState<'params' | 'headers' | 'body'>('params')
  const [response, setResponse] = useState<ProxyResponse | null>(null)
  const [sending, setSending] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState('')
  const [syncNote, setSyncNote] = useState('')

  const activeEnv = useMemo(
    () => environments.find((e) => e.is_active) || environments[0] || null,
    [environments],
  )

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      try {
        const [wsList, cols, envs, mems] = await Promise.all([
          api.listWorkspaces(),
          api.listCollections(wid),
          api.listEnvironments(wid),
          api.listMembers(wid),
        ])
        if (cancelled) return
        const ws = wsList.find((w) => w.id === wid)
        if (ws) {
          setWorkspaceName(ws.name)
          setInviteCode(ws.invite_code)
        }
        setCollections(cols)
        setEnvironments(envs)
        setMembers(mems)

        const allReqs: ApiRequest[] = []
        for (const col of cols) {
          const rows = await api.listRequests(col.id)
          allReqs.push(...rows)
        }
        if (cancelled) return
        setRequests(allReqs)
        setActiveReqId((prev) => {
          if (prev && allReqs.some((r) => r.id === prev)) return prev
          if (allReqs[0]) {
            setDraft(allReqs[0])
            return allReqs[0].id
          }
          setDraft(null)
          return null
        })
      } catch {
        if (!cancelled) setToast('加载失败')
      }
    })()
    return () => {
      cancelled = true
    }
  }, [wid])

  useEffect(() => {
    if (!activeReqId) return
    const found = requests.find((r) => r.id === activeReqId)
    if (found) setDraft(found)
  }, [activeReqId, requests])

  const onSocketEvent = useCallback(
    (event: Record<string, unknown>) => {
      if (event.type === 'request.updated') {
        const req = event.request as ApiRequest
        setRequests((prev) => prev.map((r) => (r.id === req.id ? req : r)))
        if (req.id === activeReqId) {
          setDraft(req)
          setSyncNote(`${event.updated_by_name || '队友'} 更新了当前请求`)
        } else {
          setSyncNote(`${event.updated_by_name || '队友'} 更新了 ${req.name}`)
        }
      }
      if (event.type === 'request.created') {
        const req = event.request as ApiRequest
        setRequests((prev) => (prev.some((r) => r.id === req.id) ? prev : [...prev, req]))
        setSyncNote(`新增请求：${req.name}`)
      }
      if (event.type === 'request.deleted') {
        const rid = event.request_id as number
        setRequests((prev) => prev.filter((r) => r.id !== rid))
        if (activeReqId === rid) {
          setActiveReqId(null)
          setDraft(null)
        }
        setSyncNote('有请求被删除')
      }
      if (event.type === 'collection.created') {
        const col = event.collection as Collection
        setCollections((prev) => (prev.some((c) => c.id === col.id) ? prev : [...prev, col]))
      }
      if (event.type === 'environment.updated') {
        const env = event.environment as Environment
        setEnvironments((prev) => {
          const next = prev.map((e) => (e.id === env.id ? env : e))
          if (env.is_active) {
            return next.map((e) => ({ ...e, is_active: e.id === env.id }))
          }
          return next
        })
      }
      if (event.type === 'member.joined') {
        setSyncNote(`${event.user_name} 加入了 Workspace`)
        api.listMembers(wid).then(setMembers).catch(() => undefined)
      }
    },
    [activeReqId, wid],
  )

  const { online, connected } = useWorkspaceSocket(wid, onSocketEvent)

  async function createRequest() {
    const col = collections[0]
    if (!col) {
      setToast('请先创建 Collection')
      return
    }
    const req = await api.createRequest(col.id, {
      name: 'New Request',
      method: 'GET',
      url: '{{baseUrl}}/get',
    })
    setRequests((prev) => [...prev, req])
    setActiveReqId(req.id)
    setDraft(req)
  }

  async function createCollection() {
    const name = window.prompt('Collection 名称', 'API')
    if (!name) return
    const col = await api.createCollection(wid, name)
    setCollections((prev) => [...prev, col])
  }

  async function saveDraft() {
    if (!draft) return
    setSaving(true)
    setToast('')
    try {
      const updated = await api.updateRequest(draft.id, {
        name: draft.name,
        method: draft.method,
        url: draft.url,
        headers: draft.headers,
        params: draft.params,
        body_type: draft.body_type,
        body: draft.body,
        auth_type: draft.auth_type,
        auth: draft.auth,
        version: draft.version,
      })
      setDraft(updated)
      setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
      setToast('已保存并同步')
    } catch (err) {
      const e = err as Error & { status?: number; detail?: { detail?: { current?: ApiRequest } } }
      if (e.status === 409 && e.detail && typeof e.detail === 'object') {
        const detail = e.detail as { detail?: { current?: ApiRequest } }
        const current = detail.detail?.current
        if (current) {
          setDraft(current)
          setRequests((prev) => prev.map((r) => (r.id === current.id ? current : r)))
          setToast('版本冲突：已加载最新内容，请再次编辑保存')
        }
      } else {
        setToast('保存失败')
      }
    } finally {
      setSaving(false)
    }
  }

  async function send() {
    if (!draft) return
    setSending(true)
    setResponse(null)
    try {
      const vars = activeEnv?.variables || []
      const url = interpolate(draft.url, vars)
      const headers = draft.headers.map((h) => ({
        ...h,
        value: interpolate(h.value, vars),
      }))
      const params = draft.params.map((p) => ({
        ...p,
        value: interpolate(p.value, vars),
      }))
      const body = interpolate(draft.body || '', vars)
      const res = await api.sendProxy({
        workspace_id: wid,
        request_id: draft.id,
        method: draft.method,
        url,
        headers,
        params,
        body: draft.body_type === 'none' ? null : body,
        body_type: draft.body_type,
      })
      setResponse(res)
    } catch {
      setToast('发送失败')
    } finally {
      setSending(false)
    }
  }

  function updateKV(
    field: 'headers' | 'params',
    index: number,
    patch: Partial<KeyValue>,
  ) {
    if (!draft) return
    const list = [...draft[field]]
    list[index] = { ...list[index], ...patch }
    if (index === list.length - 1 && (patch.key || patch.value)) {
      list.push({ key: '', value: '', enabled: true })
    }
    setDraft({ ...draft, [field]: list })
  }

  async function switchEnv(id: number) {
    await api.updateEnvironment(id, { is_active: true })
    setEnvironments((prev) => prev.map((e) => ({ ...e, is_active: e.id === id })))
  }

  const requestsByCollection = useMemo(() => {
    const map = new Map<number, ApiRequest[]>()
    for (const col of collections) map.set(col.id, [])
    for (const req of requests) {
      const list = map.get(req.collection_id) || []
      list.push(req)
      map.set(req.collection_id, list)
    }
    return map
  }, [collections, requests])

  return (
    <div className="workbench">
      <header className="topbar">
        <div className="topbar-left">
          <Link to="/" className="brand">
            MyPostman
          </Link>
          <span className="sep">/</span>
          <strong>{workspaceName}</strong>
          <span className={`dot ${connected ? 'on' : 'off'}`} title={connected ? '已连接' : '未连接'} />
        </div>
        <div className="topbar-right">
          <select
            value={activeEnv?.id || ''}
            onChange={(e) => switchEnv(Number(e.target.value))}
          >
            {environments.map((env) => (
              <option key={env.id} value={env.id}>
                Env: {env.name}
              </option>
            ))}
          </select>
          <span className="pill" title="邀请码">
            邀请码 {inviteCode}
          </span>
          <span className="pill">
            在线 {online.length || 1} · 成员 {members.length}
          </span>
          <span className="muted">{user?.name}</span>
          <button className="ghost" onClick={logout}>
            退出
          </button>
        </div>
      </header>

      {(toast || syncNote) && (
        <div className="banner">
          {syncNote && <span>{syncNote}</span>}
          {toast && <span>{toast}</span>}
          <button
            className="ghost"
            onClick={() => {
              setToast('')
              setSyncNote('')
            }}
          >
            关闭
          </button>
        </div>
      )}

      <div className="workbench-body">
        <aside className="sidebar">
          <div className="sidebar-actions">
            <button onClick={createCollection}>+ Collection</button>
            <button onClick={createRequest}>+ Request</button>
          </div>
          {collections.map((col) => (
            <div key={col.id} className="col-block">
              <div className="col-title">{col.name}</div>
              <ul>
                {(requestsByCollection.get(col.id) || []).map((req) => (
                  <li key={req.id}>
                    <button
                      className={req.id === activeReqId ? 'req active' : 'req'}
                      onClick={() => setActiveReqId(req.id)}
                    >
                      <span className={`method m-${req.method.toLowerCase()}`}>{req.method}</span>
                      {req.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <div className="online-box">
            <div className="col-title">在线成员</div>
            <ul>
              {(online.length ? online : [{ user_id: user?.id || 0, user_name: user?.name || '我' }]).map(
                (u) => (
                  <li key={u.user_id}>{u.user_name}</li>
                ),
              )}
            </ul>
          </div>
        </aside>

        <section className="editor">
          {!draft ? (
            <div className="empty">选择或创建一个 Request</div>
          ) : (
            <>
              <div className="req-line">
                <select
                  value={draft.method}
                  onChange={(e) => setDraft({ ...draft, method: e.target.value })}
                >
                  {METHODS.map((m) => (
                    <option key={m} value={m}>
                      {m}
                    </option>
                  ))}
                </select>
                <input
                  className="url"
                  value={draft.url}
                  onChange={(e) => setDraft({ ...draft, url: e.target.value })}
                  placeholder="https://api.example.com/path 或 {{baseUrl}}/path"
                />
                <button className="primary" onClick={send} disabled={sending}>
                  {sending ? 'Sending…' : 'Send'}
                </button>
                <button onClick={saveDraft} disabled={saving}>
                  {saving ? 'Saving…' : 'Save'}
                </button>
              </div>
              <div className="name-line">
                <input
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                />
                <span className="muted">v{draft.version}</span>
              </div>

              <div className="tabs">
                {(['params', 'headers', 'body'] as const).map((t) => (
                  <button
                    key={t}
                    className={tab === t ? 'tab active' : 'tab'}
                    onClick={() => setTab(t)}
                  >
                    {t}
                  </button>
                ))}
              </div>

              {tab === 'params' && (
                <KVEditor
                  rows={draft.params.length ? draft.params : emptyKV()}
                  onChange={(i, patch) => updateKV('params', i, patch)}
                />
              )}
              {tab === 'headers' && (
                <KVEditor
                  rows={draft.headers.length ? draft.headers : emptyKV()}
                  onChange={(i, patch) => updateKV('headers', i, patch)}
                />
              )}
              {tab === 'body' && (
                <div className="body-editor">
                  <select
                    value={draft.body_type}
                    onChange={(e) => setDraft({ ...draft, body_type: e.target.value })}
                  >
                    <option value="none">none</option>
                    <option value="json">json</option>
                    <option value="raw">raw</option>
                  </select>
                  {draft.body_type !== 'none' && (
                    <textarea
                      value={draft.body}
                      onChange={(e) => setDraft({ ...draft, body: e.target.value })}
                      placeholder='{"hello":"world"}'
                    />
                  )}
                </div>
              )}

              <div className="response">
                <div className="response-meta">
                  <strong>Response</strong>
                  {response && (
                    <span className="muted">
                      {response.error
                        ? `Error: ${response.error}`
                        : `${response.status_code} · ${response.duration_ms} ms`}
                    </span>
                  )}
                </div>
                <pre>{response ? pretty(response.body) || response.error || '(empty)' : '点击 Send 发送请求'}</pre>
              </div>
            </>
          )}
        </section>
      </div>
    </div>
  )
}

function KVEditor({
  rows,
  onChange,
}: {
  rows: KeyValue[]
  onChange: (index: number, patch: Partial<KeyValue>) => void
}) {
  return (
    <div className="kv-table">
      {rows.map((row, i) => (
        <div className="kv-row" key={i}>
          <input
            type="checkbox"
            checked={row.enabled}
            onChange={(e) => onChange(i, { enabled: e.target.checked })}
          />
          <input
            placeholder="Key"
            value={row.key}
            onChange={(e) => onChange(i, { key: e.target.value })}
          />
          <input
            placeholder="Value"
            value={row.value}
            onChange={(e) => onChange(i, { value: e.target.value })}
          />
        </div>
      ))}
    </div>
  )
}

function pretty(body: string) {
  try {
    return JSON.stringify(JSON.parse(body), null, 2)
  } catch {
    return body
  }
}
