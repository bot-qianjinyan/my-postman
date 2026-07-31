import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError('')
    try {
      await register(name, email, password)
      navigate('/')
    } catch {
      setError('注册失败，邮箱可能已被使用')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={onSubmit}>
        <div className="brand">MyPostman</div>
        <p className="muted">创建账号，开始协作</p>
        <label>
          昵称
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          邮箱
          <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required />
        </label>
        <label>
          密码（至少 6 位）
          <input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            minLength={6}
            required
          />
        </label>
        {error && <div className="error">{error}</div>}
        <button type="submit" disabled={busy}>
          {busy ? '创建中…' : '注册'}
        </button>
        <p className="muted">
          已有账号？ <Link to="/login">登录</Link>
        </p>
      </form>
    </div>
  )
}
