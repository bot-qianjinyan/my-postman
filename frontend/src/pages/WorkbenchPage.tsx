import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type {
  ApiRequest,
  Collection,
  Comment,
  Environment,
  KeyValue,
  Member,
  MockServer,
  Monitor,
  ProxyResponse,
  RunnerResult,
} from '../api/types'
import { useAuth } from '../auth/AuthContext'
import { useWorkspaceSocket } from '../hooks/useWorkspaceSocket'
import { interpolate } from '../utils/env'

const METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS']
const PROTOCOLS = ['http', 'graphql', 'ws', 'grpc']
type View = 'editor' | 'runner' | 'mock' | 'docs' | 'monitors'
type Tab = 'params' | 'headers' | 'body' | 'pre' | 'tests' | 'proto' | 'comments'

function emptyKV(): KeyValue[] {
  return [{ key: '', value: '', enabled: true }]
}

export function WorkbenchPage() {
  const { workspaceId } = useParams()
  const wid = Number(workspaceId)
  const { user, logout } = useAuth()

  const [view, setView] = useState<View>('editor')
  const [workspaceName, setWorkspaceName] = useState('Workspace')
  const [inviteCode, setInviteCode] = useState('')
  const [members, setMembers] = useState<Member[]>([])
  const [collections, setCollections] = useState<Collection[]>([])
  const [requests, setRequests] = useState<ApiRequest[]>([])
  const [environments, setEnvironments] = useState<Environment[]>([])
  const [activeReqId, setActiveReqId] = useState<number | null>(null)
  const [draft, setDraft] = useState<ApiRequest | null>(null)
  const [tab, setTab] = useState<Tab>('params')
  const [response, setResponse] = useState<ProxyResponse | null>(null)
  const [sending, setSending] = useState(false)
  const [saving, setSaving] = useState(false)
  const [toast, setToast] = useState('')
  const [syncNote, setSyncNote] = useState('')
  const [runnerResult, setRunnerResult] = useState<RunnerResult | null>(null)
  const [mocks, setMocks] = useState<MockServer[]>([])
  const [docsMd, setDocsMd] = useState('')
  const [monitors, setMonitors] = useState<Monitor[]>([])
  const [comments, setComments] = useState<Comment[]>([])
  const [commentText, setCommentText] = useState('')
  const [openapiText, setOpenapiText] = useState('')
  const [runCollectionId, setRunCollectionId] = useState<number | ''>('')

  const activeEnv = useMemo(
    () => environments.find((e) => e.is_active) || environments[0] || null,
    [environments],
  )

  const reloadTree = useCallback(async () => {
    const [wsList, cols, envs, mems] = await Promise.all([
      api.listWorkspaces(),
      api.listCollections(wid),
      api.listEnvironments(wid),
      api.listMembers(wid),
    ])
    const ws = wsList.find((w) => w.id === wid)
    if (ws) {
      setWorkspaceName(ws.name)
      setInviteCode(ws.invite_code)
    }
    setCollections(cols)
    setEnvironments(envs)
    setMembers(mems)
    if (!runCollectionId && cols[0]) setRunCollectionId(cols[0].id)

    const allReqs: ApiRequest[] = []
    for (const col of cols) {
      allReqs.push(...(await api.listRequests(col.id)))
    }
    setRequests(allReqs)
    setActiveReqId((prev) => {
      if (prev && allReqs.some((r) => r.id === prev)) return prev
      if (allReqs[0]) {
        setDraft(normalizeReq(allReqs[0]))
        return allReqs[0].id
      }
      setDraft(null)
      return null
    })
  }, [wid, runCollectionId])

  useEffect(() => {
    reloadTree().catch(() => setToast('加载失败'))
  }, [wid])

  useEffect(() => {
    if (!activeReqId) return
    const found = requests.find((r) => r.id === activeReqId)
    if (found) setDraft(normalizeReq(found))
    api.listComments(wid, activeReqId).then(setComments).catch(() => undefined)
  }, [activeReqId, requests, wid])

  const onSocketEvent = useCallback(
    (event: Record<string, unknown>) => {
      if (event.type === 'request.updated') {
        const req = normalizeReq(event.request as ApiRequest)
        setRequests((prev) => prev.map((r) => (r.id === req.id ? req : r)))
        if (req.id === activeReqId) {
          setDraft(req)
          setSyncNote(`${event.updated_by_name || '队友'} 更新了当前请求`)
        }
      }
      if (event.type === 'request.created') {
        const req = normalizeReq(event.request as ApiRequest)
        setRequests((prev) => (prev.some((r) => r.id === req.id) ? prev : [...prev, req]))
      }
      if (event.type === 'request.deleted') {
        const rid = event.request_id as number
        setRequests((prev) => prev.filter((r) => r.id !== rid))
      }
      if (event.type === 'collection.created') {
        const col = event.collection as Collection
        setCollections((prev) => (prev.some((c) => c.id === col.id) ? prev : [...prev, col]))
      }
      if (event.type === 'environment.updated') {
        const env = event.environment as Environment
        setEnvironments((prev) =>
          prev.map((e) => ({
            ...(e.id === env.id ? env : e),
            is_active: env.is_active ? e.id === env.id : e.is_active,
          })),
        )
      }
      if (event.type === 'comment.created') {
        const c = event.comment as Comment
        setComments((prev) => [c, ...prev.filter((x) => x.id !== c.id)])
        setSyncNote(`${c.user_name} 评论了`)
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
    if (!col) return setToast('请先创建 Collection')
    const req = normalizeReq(
      await api.createRequest(col.id, {
        name: 'New Request',
        method: 'GET',
        url: '{{baseUrl}}/todos/1',
        protocol: 'http',
      }),
    )
    setRequests((prev) => [...prev, req])
    setActiveReqId(req.id)
    setDraft(req)
    setView('editor')
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
    try {
      const updated = normalizeReq(
        await api.updateRequest(draft.id, {
          ...draft,
          version: draft.version,
        }),
      )
      setDraft(updated)
      setRequests((prev) => prev.map((r) => (r.id === updated.id ? updated : r)))
      setToast('已保存并同步')
    } catch (err) {
      const e = err as Error & { status?: number; detail?: { detail?: { current?: ApiRequest } } }
      if (e.status === 409) {
        const current = e.detail?.detail?.current
        if (current) {
          const norm = normalizeReq(current)
          setDraft(norm)
          setRequests((prev) => prev.map((r) => (r.id === norm.id ? norm : r)))
          setToast('版本冲突：已加载最新内容')
        }
      } else setToast('保存失败')
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
      const res = await api.sendProxy({
        workspace_id: wid,
        request_id: draft.id,
        protocol: draft.protocol,
        method: draft.method,
        url: interpolate(draft.url, vars),
        headers: draft.headers.map((h) => ({ ...h, value: interpolate(h.value, vars) })),
        params: draft.params.map((p) => ({ ...p, value: interpolate(p.value, vars) })),
        body: draft.body_type === 'none' ? null : interpolate(draft.body || '', vars),
        body_type: draft.body_type,
        pre_request_script: draft.pre_request_script,
        test_script: draft.test_script,
        graphql_query: interpolate(draft.graphql_query || '', vars),
        graphql_variables: interpolate(draft.graphql_variables || '{}', vars),
        grpc_service: draft.grpc_service,
        grpc_method: draft.grpc_method,
        grpc_message: interpolate(draft.grpc_message || '{}', vars),
        ws_messages: (draft.ws_messages || []).map((m) => interpolate(m, vars)),
        environment_id: activeEnv?.id,
      })
      setResponse(res)
      if (res.env_updates && activeEnv) {
        setEnvironments((prev) =>
          prev.map((e) => (e.id === activeEnv.id ? { ...e, variables: res.env_updates! } : e)),
        )
      }
    } catch {
      setToast('发送失败')
    } finally {
      setSending(false)
    }
  }

  function updateKV(field: 'headers' | 'params', index: number, patch: Partial<KeyValue>) {
    if (!draft) return
    const list = [...(draft[field].length ? draft[field] : emptyKV())]
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

  async function runCollection() {
    if (!runCollectionId) return
    const result = await api.runCollection({
      workspace_id: wid,
      collection_id: Number(runCollectionId),
      environment_id: activeEnv?.id,
    })
    setRunnerResult(result)
    setToast(`Runner: ${result.passed}/${result.total} passed`)
  }

  async function importOpenAPI() {
    if (!openapiText.trim()) return
    const res = await api.importOpenAPI({
      workspace_id: wid,
      content: openapiText,
    })
    setToast(`导入 ${res.imported_count} 个接口 → ${res.collection.name}`)
    setOpenapiText('')
    await reloadTree()
  }

  async function loadExtras(next: View) {
    setView(next)
    if (next === 'mock') setMocks(await api.listMocks(wid))
    if (next === 'docs') setDocsMd((await api.getDocs(wid)).markdown)
    if (next === 'monitors') setMonitors(await api.listMonitors(wid))
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
          <span className={`dot ${connected ? 'on' : 'off'}`} />
        </div>
        <div className="topbar-right">
          <nav className="view-nav">
            {(
              [
                ['editor', 'Editor'],
                ['runner', 'Runner'],
                ['mock', 'Mock'],
                ['docs', 'Docs'],
                ['monitors', 'Monitors'],
              ] as const
            ).map(([k, label]) => (
              <button
                key={k}
                className={view === k ? 'tab active' : 'tab'}
                onClick={() => (k === 'editor' ? setView('editor') : loadExtras(k))}
              >
                {label}
              </button>
            ))}
          </nav>
          <select value={activeEnv?.id || ''} onChange={(e) => switchEnv(Number(e.target.value))}>
            {environments.map((env) => (
              <option key={env.id} value={env.id}>
                Env: {env.name}
              </option>
            ))}
          </select>
          <span className="pill">邀请码 {inviteCode}</span>
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
                      onClick={() => {
                        setActiveReqId(req.id)
                        setView('editor')
                      }}
                    >
                      <span className={`method m-${req.method.toLowerCase()}`}>
                        {(req.protocol || 'http') === 'http' ? req.method : req.protocol}
                      </span>
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
              {(online.length
                ? online
                : [{ user_id: user?.id || 0, user_name: user?.name || '我' }]
              ).map((u) => (
                <li key={u.user_id}>{u.user_name}</li>
              ))}
            </ul>
          </div>
        </aside>

        <section className="editor">
          {view === 'editor' && (
            <>
              {!draft ? (
                <div className="empty">选择或创建一个 Request</div>
              ) : (
                <>
                  <div className="req-line protocol-line">
                    <select
                      value={draft.protocol}
                      onChange={(e) => setDraft({ ...draft, protocol: e.target.value })}
                    >
                      {PROTOCOLS.map((p) => (
                        <option key={p} value={p}>
                          {p}
                        </option>
                      ))}
                    </select>
                    {draft.protocol === 'http' && (
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
                    )}
                    <input
                      className="url"
                      value={draft.url}
                      onChange={(e) => setDraft({ ...draft, url: e.target.value })}
                      placeholder={
                        draft.protocol === 'grpc'
                          ? 'localhost:50051'
                          : draft.protocol === 'ws'
                            ? 'wss://echo.websocket.events'
                            : 'https://api.example.com 或 {{baseUrl}}/path'
                      }
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
                    {(
                      [
                        'params',
                        'headers',
                        'body',
                        'pre',
                        'tests',
                        'proto',
                        'comments',
                      ] as Tab[]
                    ).map((t) => (
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
                        />
                      )}
                    </div>
                  )}
                  {tab === 'pre' && (
                    <textarea
                      className="script"
                      value={draft.pre_request_script}
                      onChange={(e) => setDraft({ ...draft, pre_request_script: e.target.value })}
                      placeholder={'# Python pm API\npm.environment.set("token", "demo")'}
                    />
                  )}
                  {tab === 'tests' && (
                    <textarea
                      className="script"
                      value={draft.test_script}
                      onChange={(e) => setDraft({ ...draft, test_script: e.target.value })}
                      placeholder={
                        "pm.test('Status 200', lambda: pm.expect(pm.response.code).to_equal(200))"
                      }
                    />
                  )}
                  {tab === 'proto' && (
                    <div className="body-editor">
                      {draft.protocol === 'graphql' && (
                        <>
                          <label>GraphQL Query</label>
                          <textarea
                            value={draft.graphql_query}
                            onChange={(e) => setDraft({ ...draft, graphql_query: e.target.value })}
                          />
                          <label>Variables JSON</label>
                          <textarea
                            value={draft.graphql_variables}
                            onChange={(e) =>
                              setDraft({ ...draft, graphql_variables: e.target.value })
                            }
                          />
                        </>
                      )}
                      {draft.protocol === 'ws' && (
                        <>
                          <label>Messages（每行一条）</label>
                          <textarea
                            value={(draft.ws_messages || []).join('\n')}
                            onChange={(e) =>
                              setDraft({
                                ...draft,
                                ws_messages: e.target.value.split('\n').filter(Boolean),
                              })
                            }
                          />
                        </>
                      )}
                      {draft.protocol === 'grpc' && (
                        <>
                          <input
                            placeholder="service"
                            value={draft.grpc_service}
                            onChange={(e) => setDraft({ ...draft, grpc_service: e.target.value })}
                          />
                          <input
                            placeholder="method"
                            value={draft.grpc_method}
                            onChange={(e) => setDraft({ ...draft, grpc_method: e.target.value })}
                          />
                          <textarea
                            value={draft.grpc_message}
                            onChange={(e) => setDraft({ ...draft, grpc_message: e.target.value })}
                            placeholder="{}"
                          />
                        </>
                      )}
                      {draft.protocol === 'http' && (
                        <p className="muted">HTTP 协议无需额外 proto 配置。</p>
                      )}
                    </div>
                  )}
                  {tab === 'comments' && (
                    <div className="comments">
                      <div className="comment-form">
                        <textarea
                          value={commentText}
                          onChange={(e) => setCommentText(e.target.value)}
                          placeholder="写评论，可用 @成员名 提及"
                        />
                        <button
                          onClick={async () => {
                            if (!commentText.trim() || !draft) return
                            const c = await api.createComment(wid, commentText, draft.id)
                            setComments((prev) => [c, ...prev])
                            setCommentText('')
                          }}
                        >
                          发送评论
                        </button>
                      </div>
                      <ul className="comment-list">
                        {comments.map((c) => (
                          <li key={c.id}>
                            <strong>{c.user_name}</strong>
                            <span className="muted">
                              {c.mentions?.length ? ` · @${c.mentions.length}` : ''}
                            </span>
                            <p>{c.body}</p>
                          </li>
                        ))}
                      </ul>
                      <p className="muted">成员：{members.map((m) => m.name).join(', ')}</p>
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
                    {response?.assertions && response.assertions.length > 0 && (
                      <ul className="assert-list">
                        {response.assertions.map((a, i) => (
                          <li key={i} className={a.passed ? 'ok' : 'bad'}>
                            {a.passed ? '✓' : '✗'} {a.name}
                            {a.error ? ` — ${a.error}` : ''}
                          </li>
                        ))}
                      </ul>
                    )}
                    <pre>
                      {response
                        ? pretty(response.body) || response.error || '(empty)'
                        : '点击 Send 发送请求'}
                    </pre>
                  </div>
                </>
              )}
            </>
          )}

          {view === 'runner' && (
            <div className="panel">
              <h2>Collection Runner</h2>
              <div className="row">
                <select
                  value={runCollectionId}
                  onChange={(e) => setRunCollectionId(Number(e.target.value))}
                >
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <button className="primary" onClick={runCollection}>
                  Run
                </button>
                <button
                  onClick={async () => {
                    if (!runCollectionId) return
                    const data = await api.exportPostman(Number(runCollectionId))
                    downloadJson(`${collections.find((c) => c.id === runCollectionId)?.name || 'collection'}.postman_collection.json`, data)
                  }}
                >
                  Export Postman JSON
                </button>
              </div>
              <h3>OpenAPI 导入</h3>
              <textarea
                value={openapiText}
                onChange={(e) => setOpenapiText(e.target.value)}
                placeholder="粘贴 OpenAPI 3.x JSON/YAML"
              />
              <button onClick={importOpenAPI}>Import OpenAPI</button>
              {runnerResult && (
                <div className="runner-result">
                  <p>
                    {runnerResult.status.toUpperCase()} · {runnerResult.passed}/
                    {runnerResult.total} passed
                  </p>
                  <ul>
                    {runnerResult.items.map((item) => (
                      <li key={item.request_id} className={item.passed ? 'ok' : 'bad'}>
                        {item.passed ? '✓' : '✗'} {item.name} [{item.status_code}]{' '}
                        {item.duration_ms}ms
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="muted">
                CLI: <code>cd backend && python cli.py run collection.json -e env.json</code>
              </p>
            </div>
          )}

          {view === 'mock' && (
            <div className="panel">
              <h2>Mock Servers</h2>
              <button
                className="primary"
                onClick={async () => {
                  const m = await api.createMock(wid, 'Demo Mock')
                  setMocks((prev) => [...prev, m])
                }}
              >
                + Create Mock
              </button>
              <ul className="card-list">
                {mocks.map((m) => (
                  <li key={m.id}>
                    <strong>{m.name}</strong>
                    <div className="muted">{m.base_url}</div>
                    <ul>
                      {m.routes.map((r) => (
                        <li key={r.id}>
                          {r.method} {r.path} → {r.status_code}
                        </li>
                      ))}
                    </ul>
                    <button
                      className="ghost"
                      onClick={async () => {
                        await api.deleteMock(m.id)
                        setMocks((prev) => prev.filter((x) => x.id !== m.id))
                      }}
                    >
                      Delete
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {view === 'docs' && (
            <div className="panel">
              <h2>Auto Docs</h2>
              <button onClick={async () => setDocsMd((await api.getDocs(wid)).markdown)}>
                Refresh
              </button>
              <pre className="docs-md">{docsMd || '暂无文档'}</pre>
            </div>
          )}

          {view === 'monitors' && (
            <div className="panel">
              <h2>Monitors</h2>
              <div className="row">
                <select
                  value={runCollectionId}
                  onChange={(e) => setRunCollectionId(Number(e.target.value))}
                >
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
                <button
                  className="primary"
                  onClick={async () => {
                    if (!runCollectionId) return
                    const m = await api.createMonitor(wid, {
                      name: `Monitor ${collections.find((c) => c.id === runCollectionId)?.name}`,
                      collection_id: Number(runCollectionId),
                      environment_id: activeEnv?.id,
                      interval_minutes: 5,
                    })
                    setMonitors((prev) => [m, ...prev])
                  }}
                >
                  + Monitor
                </button>
              </div>
              <ul className="card-list">
                {monitors.map((m) => (
                  <li key={m.id}>
                    <strong>{m.name}</strong>
                    <div className="muted">
                      every {m.interval_minutes}m · {m.last_status} · {m.last_summary || 'never run'}
                    </div>
                    <div className="row">
                      <button
                        onClick={async () => {
                          const r = await api.runMonitor(m.id)
                          setToast(`Monitor run: ${r.passed}/${r.total}`)
                          setMonitors(await api.listMonitors(wid))
                        }}
                      >
                        Run now
                      </button>
                      <button
                        onClick={async () => {
                          await api.updateMonitor(m.id, { is_enabled: !m.is_enabled })
                          setMonitors(await api.listMonitors(wid))
                        }}
                      >
                        {m.is_enabled ? 'Disable' : 'Enable'}
                      </button>
                      <button
                        className="ghost"
                        onClick={async () => {
                          await api.deleteMonitor(m.id)
                          setMonitors((prev) => prev.filter((x) => x.id !== m.id))
                        }}
                      >
                        Delete
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

function normalizeReq(req: ApiRequest): ApiRequest {
  return {
    ...req,
    protocol: req.protocol || 'http',
    description: req.description || '',
    pre_request_script: req.pre_request_script || '',
    test_script: req.test_script || '',
    graphql_query: req.graphql_query || '',
    graphql_variables: req.graphql_variables || '{}',
    grpc_service: req.grpc_service || '',
    grpc_method: req.grpc_method || '',
    grpc_message: req.grpc_message || '{}',
    ws_messages: req.ws_messages || [],
    headers: req.headers || [],
    params: req.params || [],
  }
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

function downloadJson(filename: string, data: unknown) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
