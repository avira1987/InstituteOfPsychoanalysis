import React, { useState, useEffect, useCallback } from 'react'
import { userApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import PopupToast from '../components/PopupToast'

const roleLabels = {
  admin: 'مدیر سیستم',
  staff: 'کارمند دفتر',
  finance: 'اپراتور مالی',
  therapist: 'درمانگر',
  student: 'دانشجو',
  supervisor: 'سوپروایزر',
  progress_committee: 'کمیته پیشرفت',
}

const roles = Object.keys(roleLabels)

const emptyCreate = () => ({
  username: '',
  password: '',
  full_name_fa: '',
  role: 'student',
  email: '',
  phone: '',
})

export default function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')
  const [toast, setToast] = useState(null)

  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(emptyCreate)

  const [editingUser, setEditingUser] = useState(null)
  const [editForm, setEditForm] = useState({})

  const [setPasswordUser, setSetPasswordUser] = useState(null)
  const [setPasswordValue, setSetPasswordValue] = useState('')
  const [setPasswordConfirm, setSetPasswordConfirm] = useState('')

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  const closeAllModals = useCallback(() => {
    setShowCreate(false)
    setEditingUser(null)
    setSetPasswordUser(null)
    setSetPasswordValue('')
    setSetPasswordConfirm('')
  }, [])

  useEffect(() => {
    loadUsers()
  }, [])

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') closeAllModals()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [closeAllModals])

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
      setCreateForm(emptyCreate())
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const openEditModal = (u) => {
    setSetPasswordUser(null)
    setSetPasswordValue('')
    setSetPasswordConfirm('')
    setEditingUser(u)
    setEditForm({
      full_name_fa: u.full_name_fa || '',
      full_name_en: u.full_name_en || '',
      role: u.role,
      email: u.email || '',
      phone: u.phone || '',
    })
  }

  const handleUpdate = async (e) => {
    e.preventDefault()
    if (!editingUser) return
    try {
      await userApi.update(editingUser.id, editForm)
      showToast('اطلاعات کاربر ویرایش شد')
      setEditingUser(null)
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const handleSetPassword = async (e) => {
    e.preventDefault()
    if (!setPasswordUser) return
    if (setPasswordValue.length < 4) {
      showToast('رمز عبور باید حداقل ۴ کاراکتر باشد', 'error')
      return
    }
    if (setPasswordValue !== setPasswordConfirm) {
      showToast('رمز عبور و تکرار آن یکسان نیستند', 'error')
      return
    }
    try {
      await userApi.update(setPasswordUser.id, { password: setPasswordValue })
      showToast(`رمز عبور برای «${setPasswordUser.full_name_fa || setPasswordUser.username}» تنظیم شد`)
      setSetPasswordUser(null)
      setSetPasswordValue('')
      setSetPasswordConfirm('')
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

  const openSetPasswordModal = (u) => {
    setEditingUser(null)
    setSetPasswordUser(u)
    setSetPasswordValue('')
    setSetPasswordConfirm('')
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
    <div className="user-management-page">
      <PopupToast toast={toast} />

      {/* مودال: ایجاد کاربر */}
      {showCreate && currentUser?.role === 'admin' && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-create-title" onClick={() => { setShowCreate(false); setCreateForm(emptyCreate()) }}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 id="modal-create-title">ایجاد کاربر جدید</h3>
              <button type="button" className="modal-close" onClick={() => { setShowCreate(false); setCreateForm(emptyCreate()) }} aria-label="بستن">&times;</button>
            </div>
            <div className="modal-body">
              <form onSubmit={handleCreate} className="user-mgmt-modal-form">
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
                <div className="user-mgmt-modal-actions">
                  <button className="btn btn-primary" type="submit">ایجاد</button>
                  <button className="btn btn-outline" type="button" onClick={() => { setShowCreate(false); setCreateForm(emptyCreate()) }}>انصراف</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* مودال: ویرایش کاربر */}
      {editingUser && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-edit-title" onClick={() => setEditingUser(null)}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 id="modal-edit-title">ویرایش کاربر</h3>
              <button type="button" className="modal-close" onClick={() => setEditingUser(null)} aria-label="بستن">&times;</button>
            </div>
            <div className="modal-body">
              <p className="user-mgmt-modal-lead">
                <strong>{editingUser.full_name_fa || editingUser.username}</strong>
                <span className="user-mgmt-modal-meta" dir="ltr">{editingUser.username}</span>
              </p>
              <form onSubmit={handleUpdate} className="user-mgmt-modal-form">
                <div className="form-group">
                  <label className="form-label">نام فارسی</label>
                  <input className="form-input" value={editForm.full_name_fa} onChange={(e) => setEditForm({ ...editForm, full_name_fa: e.target.value })} />
                </div>
                <div className="form-group">
                  <label className="form-label">نقش</label>
                  <select className="form-input" value={editForm.role} onChange={(e) => setEditForm({ ...editForm, role: e.target.value })}>
                    {roles.map((r) => <option key={r} value={r}>{roleLabels[r]}</option>)}
                  </select>
                </div>
                <div className="form-group">
                  <label className="form-label">ایمیل</label>
                  <input className="form-input" type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} style={{ direction: 'ltr' }} />
                </div>
                <div className="form-group">
                  <label className="form-label">تلفن</label>
                  <input className="form-input" value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} style={{ direction: 'ltr' }} />
                </div>
                <div className="user-mgmt-modal-actions">
                  <button className="btn btn-primary" type="submit">ذخیره تغییرات</button>
                  <button className="btn btn-outline" type="button" onClick={() => setEditingUser(null)}>انصراف</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* مودال: تنظیم رمز عبور */}
      {setPasswordUser && (
        <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-pw-title" onClick={() => { setSetPasswordUser(null); setSetPasswordValue(''); setSetPasswordConfirm('') }}>
          <div className="modal modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 id="modal-pw-title">تنظیم رمز عبور</h3>
              <button type="button" className="modal-close" onClick={() => { setSetPasswordUser(null); setSetPasswordValue(''); setSetPasswordConfirm('') }} aria-label="بستن">&times;</button>
            </div>
            <div className="modal-body">
              <p className="user-mgmt-modal-lead">
                برای <strong>{setPasswordUser.full_name_fa || setPasswordUser.username}</strong>
                <span className="user-mgmt-modal-meta" dir="ltr">({setPasswordUser.username})</span>
              </p>
              <form onSubmit={handleSetPassword}>
                <div className="form-group">
                  <label className="form-label">رمز عبور جدید *</label>
                  <input
                    className="form-input"
                    type="password"
                    value={setPasswordValue}
                    onChange={(e) => setSetPasswordValue(e.target.value)}
                    placeholder="حداقل ۴ کاراکتر"
                    minLength={4}
                    autoComplete="new-password"
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">تکرار رمز عبور *</label>
                  <input
                    className="form-input"
                    type="password"
                    value={setPasswordConfirm}
                    onChange={(e) => setSetPasswordConfirm(e.target.value)}
                    placeholder="همان رمز را دوباره وارد کنید"
                    autoComplete="new-password"
                  />
                </div>
                <div className="user-mgmt-modal-actions">
                  <button className="btn btn-primary" type="submit">ذخیره رمز</button>
                  <button className="btn btn-outline" type="button" onClick={() => { setSetPasswordUser(null); setSetPasswordValue(''); setSetPasswordConfirm('') }}>انصراف</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت کاربران</h1>
          <p className="page-subtitle">ایجاد و مدیریت حساب‌های کاربری | مجموع: {users.length} کاربر</p>
        </div>
        {currentUser?.role === 'admin' && (
          <button type="button" className="btn btn-primary" onClick={() => setShowCreate(true)}>
            + کاربر جدید
          </button>
        )}
      </div>

      <div className="card user-mgmt-toolbar">
        <div className="user-mgmt-toolbar-inner">
          <input
            className="form-input user-mgmt-search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجو: نام کاربری، نام یا ایمیل..."
          />
          <div className="user-mgmt-role-chips">
            <button type="button" className={`btn ${roleFilter === '' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setRoleFilter('')}>همه</button>
            {roles.map((r) => (
              <button key={r} type="button" className={`btn ${roleFilter === r ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setRoleFilter(r)}>
                {roleLabels[r]}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card user-management-card">
        <div className="user-management-table-wrap">
          <table className="table-users">
            <thead>
              <tr>
                <th>کاربری</th>
                <th>نام</th>
                <th>نقش</th>
                <th>ایمیل</th>
                <th>تلفن</th>
                <th>وضعیت</th>
                <th>تاریخ</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="8" className="table-users-empty">در حال بارگذاری...</td></tr>
              ) : filteredUsers.length === 0 ? (
                <tr><td colSpan="8" className="table-users-empty">کاربری یافت نشد</td></tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id} className="table-users-row" style={{ opacity: u.is_active ? 1 : 0.55 }}>
                    <td className="table-users-cell table-users-cell-ellipsis" title={u.username}><strong>{u.username}</strong></td>
                    <td className="table-users-cell table-users-cell-ellipsis" title={u.full_name_fa || ''}>{u.full_name_fa || '-'}</td>
                    <td className="table-users-cell table-users-cell-role"><span className="badge badge-primary badge-tight">{roleLabels[u.role] || u.role}</span></td>
                    <td className="table-users-cell table-users-cell-ltr table-users-cell-ellipsis" title={u.email || ''}>{u.email || '-'}</td>
                    <td className="table-users-cell table-users-cell-ltr table-users-cell-ellipsis" title={u.phone || ''}>{u.phone || '-'}</td>
                    <td className="table-users-cell">
                      <span className={`badge ${u.is_active ? 'badge-success' : 'badge-danger'} badge-tight`}>
                        {u.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td className="table-users-cell table-users-cell-date">
                      {u.created_at ? new Date(u.created_at).toLocaleDateString('fa-IR') : '-'}
                    </td>
                    <td className="table-users-cell table-users-cell-actions">
                      <div className="user-mgmt-actions">
                        <button type="button" className="btn btn-outline btn-xs" onClick={() => openEditModal(u)}>ویرایش</button>
                        <button
                          type="button"
                          className="btn btn-outline btn-xs"
                          onClick={() => openSetPasswordModal(u)}
                          title="تنظیم رمز عبور برای ورود با نام کاربری"
                        >
                          تنظیم رمز
                        </button>
                        {currentUser?.role === 'admin' && (
                          <button
                            type="button"
                            className={`btn btn-xs ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                            onClick={() => handleToggleActive(u)}
                            disabled={u.id === currentUser?.id}
                          >
                            {u.is_active ? 'غیرفعال' : 'فعال'}
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
