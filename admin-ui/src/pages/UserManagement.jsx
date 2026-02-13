import React, { useState, useEffect } from 'react'
import { userApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'

const roleLabels = {
  admin: 'مدیر سیستم',
  staff: 'کارمند دفتر',
  therapist: 'درمانگر',
  student: 'دانشجو',
  supervisor: 'سوپروایزر',
  progress_committee: 'کمیته پیشرفت',
}

const roles = Object.keys(roleLabels)

export default function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [toast, setToast] = useState(null)

  // Create form
  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState({
    username: '', password: '', full_name_fa: '', role: 'student', email: '', phone: '',
  })

  // Edit form
  const [editingId, setEditingId] = useState(null)
  const [editForm, setEditForm] = useState({})

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    loadUsers()
  }, [])

  const loadUsers = async () => {
    try {
      const res = await userApi.list()
      setUsers(res.data)
    } catch (err) {
      console.error('Failed to load users:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      await userApi.create(createForm)
      showToast('کاربر جدید با موفقیت ایجاد شد')
      setShowCreate(false)
      setCreateForm({ username: '', password: '', full_name_fa: '', role: 'student', email: '', phone: '' })
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const startEdit = (u) => {
    setEditForm({
      full_name_fa: u.full_name_fa || '',
      full_name_en: u.full_name_en || '',
      role: u.role,
      email: u.email || '',
      phone: u.phone || '',
    })
    setEditingId(u.id)
  }

  const handleUpdate = async (e) => {
    e.preventDefault()
    try {
      await userApi.update(editingId, editForm)
      showToast('اطلاعات کاربر ویرایش شد')
      setEditingId(null)
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const handleToggleActive = async (u) => {
    if (u.id === currentUser?.id) {
      showToast('نمی‌توانید حساب خودتان را غیرفعال کنید', 'error')
      return
    }
    try {
      if (u.is_active) {
        await userApi.delete(u.id)
        showToast(`کاربر '${u.username}' غیرفعال شد`)
      } else {
        await userApi.update(u.id, { is_active: true })
        showToast(`کاربر '${u.username}' فعال شد`)
      }
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const filteredUsers = users.filter((u) => {
    if (roleFilter && u.role !== roleFilter) return false
    if (search) {
      const q = search.toLowerCase()
      return (
        u.username.toLowerCase().includes(q) ||
        (u.full_name_fa || '').includes(search) ||
        (u.email || '').toLowerCase().includes(q)
      )
    }
    return true
  })

  return (
    <div>
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت کاربران</h1>
          <p className="page-subtitle">ایجاد و مدیریت حساب‌های کاربری | مجموع: {users.length} کاربر</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'لغو' : '+ کاربر جدید'}
        </button>
      </div>

      {/* Create User Form */}
      {showCreate && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 className="card-title" style={{ marginBottom: '1rem' }}>ایجاد کاربر جدید</h3>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">نام کاربری *</label>
              <input className="form-input" value={createForm.username} onChange={(e) => setCreateForm({ ...createForm, username: e.target.value })} required style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group">
              <label className="form-label">رمز عبور *</label>
              <input className="form-input" type="password" value={createForm.password} onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })} required />
            </div>
            <div className="form-group">
              <label className="form-label">نام کامل (فارسی)</label>
              <input className="form-input" value={createForm.full_name_fa} onChange={(e) => setCreateForm({ ...createForm, full_name_fa: e.target.value })} />
            </div>
            <div className="form-group">
              <label className="form-label">نقش *</label>
              <select className="form-input" value={createForm.role} onChange={(e) => setCreateForm({ ...createForm, role: e.target.value })}>
                {roles.map((r) => <option key={r} value={r}>{roleLabels[r]} ({r})</option>)}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">ایمیل</label>
              <input className="form-input" type="email" value={createForm.email} onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })} style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group">
              <label className="form-label">شماره تلفن</label>
              <input className="form-input" value={createForm.phone} onChange={(e) => setCreateForm({ ...createForm, phone: e.target.value })} style={{ direction: 'ltr' }} />
            </div>
            <div><button className="btn btn-primary" type="submit">ایجاد</button></div>
          </form>
        </div>
      )}

      {/* Search and Filter */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            className="form-input"
            style={{ flex: 1, minWidth: '200px' }}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجو بر اساس نام کاربری، نام یا ایمیل..."
          />
          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button className={`btn ${roleFilter === '' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setRoleFilter('')}>همه</button>
            {roles.map((r) => (
              <button key={r} className={`btn ${roleFilter === r ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setRoleFilter(r)}>
                {roleLabels[r]}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Users Table */}
      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>نام کاربری</th>
                <th>نام</th>
                <th>نقش</th>
                <th>ایمیل</th>
                <th>تلفن</th>
                <th>وضعیت</th>
                <th>تاریخ ایجاد</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
              ) : filteredUsers.length === 0 ? (
                <tr><td colSpan="8" style={{ textAlign: 'center', padding: '2rem' }}>کاربری یافت نشد</td></tr>
              ) : (
                filteredUsers.map((u) => (
                  <React.Fragment key={u.id}>
                    <tr style={{ opacity: u.is_active ? 1 : 0.6 }}>
                      <td><strong>{u.username}</strong></td>
                      <td>{u.full_name_fa || '-'}</td>
                      <td><span className="badge badge-primary">{roleLabels[u.role] || u.role}</span></td>
                      <td style={{ direction: 'ltr', textAlign: 'right', fontSize: '0.85rem' }}>{u.email || '-'}</td>
                      <td style={{ direction: 'ltr', textAlign: 'right', fontSize: '0.85rem' }}>{u.phone || '-'}</td>
                      <td>
                        <span className={`badge ${u.is_active ? 'badge-success' : 'badge-danger'}`}>
                          {u.is_active ? 'فعال' : 'غیرفعال'}
                        </span>
                      </td>
                      <td style={{ fontSize: '0.8rem' }}>
                        {u.created_at ? new Date(u.created_at).toLocaleDateString('fa-IR') : '-'}
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          <button className="btn btn-outline btn-sm" onClick={() => editingId === u.id ? setEditingId(null) : startEdit(u)}>
                            {editingId === u.id ? 'لغو' : 'ویرایش'}
                          </button>
                          <button
                            className={`btn btn-sm ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                            onClick={() => handleToggleActive(u)}
                            disabled={u.id === currentUser?.id}
                          >
                            {u.is_active ? 'غیرفعال' : 'فعال'}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {editingId === u.id && (
                      <tr>
                        <td colSpan="8" style={{ background: 'var(--bg)', padding: '1rem' }}>
                          <form onSubmit={handleUpdate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr auto', gap: '0.75rem', alignItems: 'flex-end' }}>
                            <div className="form-group" style={{ marginBottom: 0 }}>
                              <label className="form-label">نام فارسی</label>
                              <input className="form-input" value={editForm.full_name_fa} onChange={(e) => setEditForm({ ...editForm, full_name_fa: e.target.value })} />
                            </div>
                            <div className="form-group" style={{ marginBottom: 0 }}>
                              <label className="form-label">نقش</label>
                              <select className="form-input" value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>
                                {roles.map((r) => <option key={r} value={r}>{roleLabels[r]}</option>)}
                              </select>
                            </div>
                            <div className="form-group" style={{ marginBottom: 0 }}>
                              <label className="form-label">ایمیل</label>
                              <input className="form-input" type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} style={{ direction: 'ltr' }} />
                            </div>
                            <div className="form-group" style={{ marginBottom: 0 }}>
                              <label className="form-label">تلفن</label>
                              <input className="form-input" value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} style={{ direction: 'ltr' }} />
                            </div>
                            <button className="btn btn-primary btn-sm" type="submit">ذخیره</button>
                          </form>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
