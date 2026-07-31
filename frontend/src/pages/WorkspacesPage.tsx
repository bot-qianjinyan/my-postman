import { useEffect, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { Workspace } from '../api/types'
import { useAuth } from '../auth/AuthContext'

export function WorkspacesPage() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [name, setName] = useState('')
  const [invite, setInvite] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  async function refresh() {
    const rows = await api.listWorkspaces()
    setWorkspaces(rows)
  }

  useEffect(() => {
    refresh()
      .catch(() => setError('加载 Workspace 失败'))
      .finally(() => setLoading(false))
  }, [])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const ws = await api.createWorkspace(name.trim())
      setName('')
      navigate(`/w/${ws.id}`)
    } catch {
      setError('创建失败')
    }
  }

  async function onJoin(e: FormEvent) {
    e.preventDefault()
    setError('')
    try {
      const ws = await api.joinWorkspace(invite.trim())
      setInvite('')
      navigate(`/w/${ws.id}`)
    } catch {
      setError('邀请码无效')
    }
  }

  return (
    <div className="page">
      <header className="topbar">
        <div className="brand">MyPostman</div>
        <div className="topbar-right">
          <span className="muted">{user?.name}</span>
          <button className="ghost" onClick={logout}>
            退出
          </button>
        </div>
      </header>

      <main className="workspace-home">
        <section>
          <h1>你的 Workspace</h1>
          <p className="muted">创建团队空间，或通过邀请码加入他人 Workspace。</p>
          {error && <div className="error">{error}</div>}
          {loading ? (
            <p className="muted">加载中…</p>
          ) : workspaces.length === 0 ? (
            <p className="muted">还没有 Workspace，先创建一个吧。</p>
          ) : (
            <ul className="ws-list">
              {workspaces.map((ws) => (
                <li key={ws.id}>
                  <Link to={`/w/${ws.id}`}>
                    <strong>{ws.name}</strong>
                    <span className="muted">
                      {ws.role} · 邀请码 {ws.invite_code}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="ws-actions">
          <form onSubmit={onCreate}>
            <h2>新建 Workspace</h2>
            <input
              placeholder="例如：支付 API"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <button type="submit">创建</button>
          </form>
          <form onSubmit={onJoin}>
            <h2>加入 Workspace</h2>
            <input
              placeholder="粘贴邀请码"
              value={invite}
              onChange={(e) => setInvite(e.target.value)}
              required
            />
            <button type="submit">加入</button>
          </form>
        </aside>
      </main>
    </div>
  )
}
