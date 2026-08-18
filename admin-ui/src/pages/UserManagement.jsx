import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { userApi, studentApi, processApi, processExecApi } from '../services/api'
import { useAuth } from '../contexts/AuthContext'
import { useToast } from '../contexts/ToastContext'
import StudentRegistrationExtendedFields from '../components/StudentRegistrationExtendedFields'
import RegistrationCourseTypeEditor from '../components/RegistrationCourseTypeEditor'
import {
  buildRegistrationProfilePayload,
  emptyExtendedRegistrationFields,
  extendedFieldsFromExtra,
  validateExtendedRegistrationClient,
} from '../utils/studentRegistrationProfile'
import { labelRoleFa, ROLE_LABELS_FA_MAP } from '../utils/roleLabels'
import { getUserRoles, userHasRole } from '../utils/userRoles'
import { getManualStartScope } from '../utils/processStartScope'
import { sortProcessNavItems } from '../utils/processNavOrder'
import { groupProcessNavItemsByCategory } from '../utils/processNavCategories'
import { formatStudentCodeDisplay, labelProcess } from '../utils/processDisplay'

const ROLE_PICKER_EXCLUDE = new Set(['system'])
const ROLE_PICKER_PIN = ['admin', 'internal_manager', 'staff', 'student', 'deputy_education', 'finance']
const portalRoleOptions = [
  ...ROLE_PICKER_PIN.filter((r) => ROLE_LABELS_FA_MAP[r]),
  ...Object.keys(ROLE_LABELS_FA_MAP)
    .filter((r) => !ROLE_PICKER_EXCLUDE.has(r) && !ROLE_PICKER_PIN.includes(r))
    .sort((a, b) => labelRoleFa(a, { includeCode: false }).localeCompare(
      labelRoleFa(b, { includeCode: false }),
      'fa',
    )),
]

const USER_TABLE_COLS_STORAGE_KEY = 'anistito.user-mgmt.col-widths.v1'
const USER_TABLE_COLS = [
  { key: 'username', label: 'کاربری', defaultWidth: 120, minWidth: 72 },
  { key: 'name', label: 'نام', defaultWidth: 150, minWidth: 80 },
  { key: 'role', label: 'نقش', defaultWidth: 110, minWidth: 72 },
  { key: 'student_code', label: 'شماره دانشجویی', defaultWidth: 130, minWidth: 90 },
  { key: 'national_code', label: 'کد ملی', defaultWidth: 110, minWidth: 80 },
  { key: 'status', label: 'وضعیت', defaultWidth: 80, minWidth: 64 },
  { key: 'date', label: 'تاریخ', defaultWidth: 100, minWidth: 72 },
  { key: 'actions', label: 'عملیات', defaultWidth: 320, minWidth: 160 },
]

function defaultUserTableColWidths() {
  return Object.fromEntries(USER_TABLE_COLS.map((c) => [c.key, c.defaultWidth]))
}

function loadUserTableColWidths() {
  const defaults = defaultUserTableColWidths()
  try {
    const raw = localStorage.getItem(USER_TABLE_COLS_STORAGE_KEY)
    if (!raw) return defaults
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return defaults
    const next = { ...defaults }
    for (const col of USER_TABLE_COLS) {
      const n = Number(parsed[col.key])
      if (Number.isFinite(n)) next[col.key] = Math.max(col.minWidth, Math.round(n))
    }
    return next
  } catch {
    return defaults
  }
}

const emptyCreate = () => ({
  username: '',
  password: '',
  full_name_fa: '',
  role: 'student',
  roles: ['student'],
  email: '',
  phone: '',
})

function apiErrorMessage(err) {
  const d = err?.response?.data?.detail
  if (typeof d === 'string' && d.trim()) return d
  if (Array.isArray(d)) {
    return d.map((x) => (typeof x === 'string' ? x : x?.msg || x?.detail || '')).filter(Boolean).join(' ')
  }
  return err?.message || 'خطای ناشناخته'
}

function toggleRoleInList(roles, code) {
  const set = new Set(roles || [])
  if (set.has(code)) {
    if (set.size <= 1) return Array.from(set)
    set.delete(code)
  } else {
    set.add(code)
  }
  return Array.from(set)
}

function RoleChipsPicker({ roles, primary, onChangeRoles, onChangePrimary, disabled }) {
  const selected = roles?.length ? roles : (primary ? [primary] : [])
  return (
    <>
      <div className="form-group" style={{ gridColumn: '1 / -1' }}>
        <label className="form-label">نقش‌ها *</label>
        <div className="rules-picker" role="group" aria-label="نقش‌ها">
          {portalRoleOptions.map((r) => {
            const on = selected.includes(r)
            return (
              <label key={r} className={`rule-chip ${on ? 'selected' : ''}`}>
                <input
                  type="checkbox"
                  checked={on}
                  disabled={disabled}
                  onChange={() => {
                    if (disabled) return
                    const next = toggleRoleInList(selected, r)
                    onChangeRoles(next)
                    if (!next.includes(primary)) {
                      onChangePrimary(next[0] || r)
                    }
                  }}
                  style={{ display: 'none' }}
                />
                <span>{labelRoleFa(r, { includeCode: false })}</span>
              </label>
            )
          })}
        </div>
      </div>
      <div className="form-group" style={{ gridColumn: '1 / -1' }}>
        <label className="form-label">نقش اصلی (صفحه ورود)</label>
        <select
          className="form-input"
          value={selected.includes(primary) ? primary : selected[0] || ''}
          disabled={disabled || selected.length === 0}
          onChange={(e) => onChangePrimary(e.target.value)}
        >
          {selected.map((r) => (
            <option key={r} value={r}>{labelRoleFa(r, { includeCode: false })}</option>
          ))}
        </select>
      </div>
    </>
  )
}

export default function UserManagement() {
  const { user: currentUser } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [roleFilter, setRoleFilter] = useState('')

  const [showCreate, setShowCreate] = useState(false)
  const [createForm, setCreateForm] = useState(emptyCreate)

  const [editingUser, setEditingUser] = useState(null)
  const [editForm, setEditForm] = useState({})
  const [regProfileForm, setRegProfileForm] = useState(emptyExtendedRegistrationFields())
  const [regProfileLoading, setRegProfileLoading] = useState(false)
  const [hasStudentProfile, setHasStudentProfile] = useState(false)
  const [studentCourseType, setStudentCourseType] = useState('introductory')
  const [studentProfileId, setStudentProfileId] = useState(null)
  const [studentCode, setStudentCode] = useState('')

  const [setPasswordUser, setSetPasswordUser] = useState(null)
  const [setPasswordValue, setSetPasswordValue] = useState('')
  const [setPasswordConfirm, setSetPasswordConfirm] = useState('')
  const [setPasswordSaving, setSetPasswordSaving] = useState(false)

  /** تأیید حذف دائمی از DB (فقط ادمین) */
  const [deleteTarget, setDeleteTarget] = useState(null)
  const { showToast } = useToast()

  const [showStartProcess, setShowStartProcess] = useState(false)
  const [startTargetUser, setStartTargetUser] = useState(null)
  const [processDefinitions, setProcessDefinitions] = useState([])
  const [colWidths, setColWidths] = useState(loadUserTableColWidths)
  const [isResizingCol, setIsResizingCol] = useState(false)
  const colWidthsRef = useRef(colWidths)
  colWidthsRef.current = colWidths

  useEffect(() => {
    try {
      localStorage.setItem(USER_TABLE_COLS_STORAGE_KEY, JSON.stringify(colWidths))
    } catch {
      /* ignore */
    }
  }, [colWidths])

  const tableMinWidth = useMemo(
    () => USER_TABLE_COLS.reduce((sum, col) => sum + (colWidths[col.key] || col.defaultWidth), 0),
    [colWidths],
  )

  const onColResizeStart = useCallback((e, colKey) => {
    e.preventDefault()
    e.stopPropagation()
    const col = USER_TABLE_COLS.find((c) => c.key === colKey)
    if (!col) return
    const startX = e.clientX
    const startWidth = colWidthsRef.current[colKey] || col.defaultWidth
    setIsResizingCol(true)

    const onMove = (ev) => {
      // جدول RTL است: کشیدن به چپ = پهن‌تر، به راست = باریک‌تر
      const next = Math.max(col.minWidth, Math.round(startWidth + (startX - ev.clientX)))
      setColWidths((prev) => (prev[colKey] === next ? prev : { ...prev, [colKey]: next }))
    }
    const onUp = () => {
      setIsResizingCol(false)
      document.removeEventListener('mousemove', onMove)
      document.removeEventListener('mouseup', onUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', onUp)
  }, [])
  const [startForm, setStartForm] = useState({ process_code: '', user_id: '' })

  const rolesInUse = useMemo(
    () => [...new Set(users.flatMap((u) => getUserRoles(u)).filter(Boolean))].sort(),
    [users],
  )

  const isAdmin = userHasRole(currentUser, 'admin', { adminBypass: false })

  const startProcessGroups = useMemo(
    () => groupProcessNavItemsByCategory(processDefinitions),
    [processDefinitions],
  )

  const closeAllModals = useCallback(() => {
    setShowCreate(false)
    setEditingUser(null)
    setSetPasswordUser(null)
    setSetPasswordValue('')
    setSetPasswordConfirm('')
    setDeleteTarget(null)
    setShowStartProcess(false)
    setStartTargetUser(null)
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
      const res = await userApi.list({ limit: 10000 })
      setUsers(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      console.error('Failed to load users:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      const payload = {
        ...createForm,
        username: (createForm.username || '').trim(),
        full_name_fa: (createForm.full_name_fa || '').trim() || null,
        email: (createForm.email || '').trim() || null,
        phone: (createForm.phone || '').trim() || null,
        roles: createForm.roles?.length ? createForm.roles : [createForm.role || 'student'],
        role: createForm.role || createForm.roles?.[0] || 'student',
      }
      await userApi.create(payload)
      showToast('کاربر جدید با موفقیت ایجاد شد')
      setShowCreate(false)
      setCreateForm(emptyCreate())
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const openStartProcess = async (u) => {
    if (!u || getUserRoles(u).every((r) => r === 'student' || r === 'applicant')) return
    setStartTargetUser(u)
    setStartForm({ process_code: '', user_id: u.id })
    try {
      const res = await processApi.list()
      const active = (Array.isArray(res.data) ? res.data : []).filter(
        (p) => p.is_active && getManualStartScope(p.code) === 'staff',
      )
      setProcessDefinitions(
        sortProcessNavItems(
          active.map((p) => ({
            ...p,
            process_code: p.code,
            label_fa: p.name_fa,
            sop_order: p.sop_order,
          })),
        ),
      )
    } catch (err) {
      console.error(err)
      setProcessDefinitions([])
    }
    setShowStartProcess(true)
  }

  const handleStartProcess = async (e) => {
    e.preventDefault()
    if (!startForm.process_code || !startForm.user_id) return
    try {
      await processExecApi.start({
        process_code: startForm.process_code,
        user_id: startForm.user_id,
      })
      showToast(`فرایند «${labelProcess(startForm.process_code)}» برای کاربر شروع شد`)
      setShowStartProcess(false)
      setStartTargetUser(null)
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const openEditModal = async (u) => {
    setDeleteTarget(null)
    setSetPasswordUser(null)
    setSetPasswordValue('')
    setSetPasswordConfirm('')
    setEditingUser(u)
    setEditForm({
      full_name_fa: u.full_name_fa || '',
      full_name_en: u.full_name_en || '',
      role: u.role,
      roles: getUserRoles(u),
      email: u.email || '',
      phone: u.phone || '',
    })
    setRegProfileForm(emptyExtendedRegistrationFields())
    setHasStudentProfile(false)
    setStudentCourseType('introductory')
    setStudentProfileId(null)
    setStudentCode(u.student_code || '')
    if (getUserRoles(u).includes('student')) {
      setRegProfileLoading(true)
      try {
        const res = await studentApi.getRegistrationProfileByUser(u.id)
        setHasStudentProfile(true)
        setStudentProfileId(res.data?.student_id || null)
        setStudentCourseType(res.data?.course_type || 'introductory')
        setStudentCode(res.data?.student_code || u.student_code || '')
        setRegProfileForm(extendedFieldsFromExtra(res.data))
        if (res.data?.email) {
          setEditForm((prev) => ({ ...prev, email: res.data.email }))
        }
      } catch {
        /* دانشجو بدون پروفایل Student — فقط ویرایش حساب کاربری */
      } finally {
        setRegProfileLoading(false)
      }
    }
  }

  const handleUpdate = async (e) => {
    e.preventDefault()
    if (!editingUser) return
    try {
      const userPatch = { ...editForm }
      // نام فارسی فقط از «اطلاعات شخصی تکمیلی» قابل تغییر است
      delete userPatch.full_name_fa
      delete userPatch.full_name_en
      const rolesNow = editForm.roles?.length ? editForm.roles : getUserRoles(editingUser)
      if (isAdmin) {
        userPatch.roles = rolesNow
        userPatch.role = rolesNow.includes(editForm.role) ? editForm.role : rolesNow[0]
      } else {
        delete userPatch.role
        delete userPatch.roles
      }
      if (rolesNow.includes('student') && hasStudentProfile) {
        const extErrors = validateExtendedRegistrationClient(regProfileForm)
        if (extErrors.length) {
          showToast(extErrors[0], 'error')
          return
        }
        const combinedName = `${(regProfileForm.first_name_fa || '').trim()} ${(regProfileForm.last_name_fa || '').trim()}`.trim()
        if (combinedName) userPatch.full_name_fa = combinedName
      }
      await userApi.update(editingUser.id, userPatch)
      if (rolesNow.includes('student') && hasStudentProfile) {
        await studentApi.updateRegistrationProfileByUser(
          editingUser.id,
          buildRegistrationProfilePayload(regProfileForm),
        )
      }
      showToast('اطلاعات کاربر ویرایش شد')
      setEditingUser(null)
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + apiErrorMessage(err), 'error')
    }
  }

  const handleRegProfileChange = (ev) => {
    setRegProfileForm((prev) => ({ ...prev, [ev.target.name]: ev.target.value }))
  }

  const handleSetPassword = async (e) => {
    e.preventDefault()
    if (!setPasswordUser || setPasswordSaving) return
    const form = e.currentTarget
    const fd = form instanceof HTMLFormElement ? new FormData(form) : null
    const typed = String(fd?.get('new_user_password') || setPasswordValue || '')
    const typedConfirm = String(fd?.get('new_user_password_confirm') || setPasswordConfirm || '')
    if (typed.length < 4) {
      showToast('رمز عبور باید حداقل ۴ کاراکتر باشد', 'error')
      return
    }
    if (typed !== typedConfirm) {
      showToast('رمز عبور و تکرار آن یکسان نیستند', 'error')
      return
    }
    setSetPasswordSaving(true)
    try {
      const res = await userApi.setPassword(setPasswordUser.id, typed)
      if (res?.data && res.data.password_set !== true) {
        showToast('سرور رمز را تأیید نکرد. دوباره تلاش کنید.', 'error')
        return
      }
      showToast(`رمز عبور برای «${setPasswordUser.full_name_fa || setPasswordUser.username}» تنظیم شد`)
      setSetPasswordUser(null)
      setSetPasswordValue('')
      setSetPasswordConfirm('')
      loadUsers()
    } catch (err) {
      showToast('خطا: ' + apiErrorMessage(err), 'error')
    } finally {
      setSetPasswordSaving(false)
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
        setUsers((prev) =>
          prev.map((row) => (String(row.id) === String(u.id) ? { ...row, is_active: false } : row))
        )
      } else {
        await userApi.update(u.id, { is_active: true })
        showToast(`کاربر '${u.username}' فعال شد`)
        setUsers((prev) =>
          prev.map((row) => (String(row.id) === String(u.id) ? { ...row, is_active: true } : row))
        )
      }
      await loadUsers()
    } catch (err) {
      showToast('خطا: ' + (err.response?.data?.detail || err.message), 'error')
    }
  }

  const handlePermanentDelete = async () => {
    if (!deleteTarget) return
    if (deleteTarget.id === currentUser?.id) {
      showToast('نمی‌توانید حساب خودتان را حذف کنید', 'error')
      return
    }
    try {
      const removedId = String(deleteTarget.id)
      await userApi.delete(deleteTarget.id, { params: { permanent: true } })
      showToast(`کاربر «${deleteTarget.username}» به‌طور دائم حذف شد`)
      setDeleteTarget(null)
      setUsers((prev) => prev.filter((u) => String(u.id) !== removedId))
      await loadUsers()
    } catch (err) {
      const d = err.response?.data?.detail
      const msg = typeof d === 'string' ? d : Array.isArray(d) ? d.map((x) => x.msg || x).join(' ') : err.message
      showToast('خطا: ' + msg, 'error')
    }
  }

  const openSetPasswordModal = (u) => {
    setDeleteTarget(null)
    setEditingUser(null)
    setSetPasswordUser(u)
    setSetPasswordValue('')
    setSetPasswordConfirm('')
  }

  const filteredUsers = users.filter((u) => {
    if (roleFilter && !getUserRoles(u).includes(roleFilter)) return false
    if (search) {
      const q = search.toLowerCase()
      const nc = (u.national_code || '').toString()
      const sc = (u.student_code || '').toString().toLowerCase()
      return (
        u.username.toLowerCase().includes(q) ||
        (u.full_name_fa || '').includes(search) ||
        nc.includes(search.replace(/\s/g, '')) ||
        sc.includes(q.replace(/\s/g, ''))
      )
    }
    return true
  })

  return (
    <div className="user-management-page">

      {/* مودال: ایجاد کاربر */}
      {showCreate && isAdmin && (
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
                <RoleChipsPicker
                  roles={createForm.roles}
                  primary={createForm.role}
                  onChangeRoles={(roles) => setCreateForm((prev) => ({
                    ...prev,
                    roles,
                    role: roles.includes(prev.role) ? prev.role : roles[0],
                  }))}
                  onChangePrimary={(role) => setCreateForm((prev) => ({ ...prev, role }))}
                />
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
                <strong>
                  {(editForm.roles || []).includes('student') && hasStudentProfile
                    ? (
                        `${(regProfileForm.first_name_fa || '').trim()} ${(regProfileForm.last_name_fa || '').trim()}`.trim()
                        || editingUser.full_name_fa
                        || editingUser.username
                      )
                    : (editingUser.full_name_fa || editingUser.username)}
                </strong>
              </p>
              <form onSubmit={handleUpdate} className="user-mgmt-modal-form">
                {isAdmin ? (
                  <RoleChipsPicker
                    roles={editForm.roles}
                    primary={editForm.role}
                    onChangeRoles={(roles) => setEditForm((prev) => ({
                      ...prev,
                      roles,
                      role: roles.includes(prev.role) ? prev.role : roles[0],
                    }))}
                    onChangePrimary={(role) => setEditForm((prev) => ({ ...prev, role }))}
                  />
                ) : (
                  <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                    <label className="form-label">نقش‌ها</label>
                    <div className="user-mgmt-role-chips">
                      {getUserRoles({ role: editForm.role, roles: editForm.roles }).map((r) => (
                        <span key={r} className="badge badge-primary badge-tight">{labelRoleFa(r, { includeCode: false })}</span>
                      ))}
                    </div>
                  </div>
                )}
                <div className="form-group">
                  <label className="form-label">تلفن</label>
                  <input className="form-input" value={editForm.phone} onChange={(e) => setEditForm({ ...editForm, phone: e.target.value })} style={{ direction: 'ltr' }} />
                </div>
                {(editForm.roles || []).includes('student') && (
                  <div className="form-group">
                    <label className="form-label">شماره دانشجویی</label>
                    <input
                      className="form-input"
                      value={studentCode ? formatStudentCodeDisplay(studentCode) : '—'}
                      readOnly
                      disabled
                      style={{ direction: 'ltr' }}
                    />
                  </div>
                )}
                {(editForm.roles || []).includes('student') && (
                  <div className="form-group">
                    <label className="form-label">ایمیل</label>
                    <input
                      className="form-input"
                      type="email"
                      value={editForm.email || ''}
                      onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
                      style={{ direction: 'ltr' }}
                    />
                  </div>
                )}
                {(editForm.roles || []).includes('student') && hasStudentProfile && (
                  <div style={{ marginTop: '0.5rem' }}>
                    {studentProfileId && (
                      <RegistrationCourseTypeEditor
                        studentId={studentProfileId}
                        initialCourseType={studentCourseType}
                        showToast={showToast}
                        onSaved={(data) => {
                          if (data?.course_type) setStudentCourseType(data.course_type)
                        }}
                      />
                    )}
                    <h4 style={{ margin: '0 0 0.75rem', fontSize: '1rem' }}>اطلاعات تکمیلی ثبت‌نام</h4>
                    {regProfileLoading ? (
                      <p className="muted" style={{ fontSize: '0.88rem' }}>در حال بارگذاری…</p>
                    ) : (
                      <StudentRegistrationExtendedFields
                        form={regProfileForm}
                        onChange={handleRegProfileChange}
                        className="pub-register-form"
                      />
                    )}
                  </div>
                )}
                <div className="user-mgmt-modal-actions">
                  <button className="btn btn-primary" type="submit">ذخیره تغییرات</button>
                  <button className="btn btn-outline" type="button" onClick={() => setEditingUser(null)}>انصراف</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* مودال: حذف دائمی کاربر */}
      {deleteTarget && isAdmin && (
        <div
          className="modal-overlay"
          role="dialog"
          aria-modal="true"
          aria-labelledby="modal-del-user-title"
          onClick={() => setDeleteTarget(null)}
        >
          <div className="modal modal-sm" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 id="modal-del-user-title">حذف دائمی کاربر</h3>
              <button type="button" className="modal-close" onClick={() => setDeleteTarget(null)} aria-label="بستن">&times;</button>
            </div>
            <div className="modal-body">
              <p className="user-mgmt-modal-lead">
                حذف <strong>{deleteTarget.full_name_fa || deleteTarget.username}</strong>
                <span className="user-mgmt-modal-meta" dir="ltr">({deleteTarget.username})</span>
                {' '}غیرقابل بازگشت است؛ در صورت دانشجو، پروفایل و داده‌های وابستهٔ قابل‌حذف نیز پاک می‌شود.
              </p>
              <div className="user-mgmt-modal-actions">
                <button type="button" className="btn btn-danger" onClick={handlePermanentDelete}>
                  بله، حذف دائمی
                </button>
                <button type="button" className="btn btn-outline" onClick={() => setDeleteTarget(null)}>انصراف</button>
              </div>
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
              <p className="user-mgmt-modal-meta" style={{ marginBottom: '0.75rem' }}>
                ورود با این رمز از مسیر «ورود پرسنل و مدیران» با همین نام کاربری است، نه تب پیامک.
              </p>
              <form onSubmit={handleSetPassword} autoComplete="off">
                <input type="text" name="username" value={setPasswordUser.username || ''} readOnly tabIndex={-1} aria-hidden="true" autoComplete="username" style={{ position: 'absolute', opacity: 0, height: 0, width: 0, pointerEvents: 'none' }} />
                <div className="form-group">
                  <label className="form-label">رمز عبور جدید *</label>
                  <input
                    className="form-input"
                    type="password"
                    name="new_user_password"
                    value={setPasswordValue}
                    onChange={(e) => setSetPasswordValue(e.target.value)}
                    placeholder="حداقل ۴ کاراکتر"
                    minLength={4}
                    required
                    autoComplete="new-password"
                    disabled={setPasswordSaving}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">تکرار رمز عبور *</label>
                  <input
                    className="form-input"
                    type="password"
                    name="new_user_password_confirm"
                    value={setPasswordConfirm}
                    onChange={(e) => setSetPasswordConfirm(e.target.value)}
                    placeholder="همان رمز را دوباره وارد کنید"
                    minLength={4}
                    required
                    autoComplete="new-password"
                    disabled={setPasswordSaving}
                  />
                </div>
                <div className="user-mgmt-modal-actions">
                  <button className="btn btn-primary" type="submit" disabled={setPasswordSaving}>
                    {setPasswordSaving ? 'در حال ذخیره...' : 'ذخیره رمز'}
                  </button>
                  <button className="btn btn-outline" type="button" disabled={setPasswordSaving} onClick={() => { setSetPasswordUser(null); setSetPasswordValue(''); setSetPasswordConfirm('') }}>انصراف</button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {showStartProcess && startTargetUser && (
        <div className="modal-overlay" onClick={() => { setShowStartProcess(false); setStartTargetUser(null) }}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>شروع فرایند برای کاربر</h3>
              <button
                type="button"
                className="modal-close"
                onClick={() => { setShowStartProcess(false); setStartTargetUser(null) }}
                aria-label="بستن"
              >
                &times;
              </button>
            </div>
            <div className="modal-body">
              <p className="user-mgmt-modal-lead" style={{ marginBottom: '0.85rem' }}>
                برای <strong>{startTargetUser.full_name_fa || startTargetUser.username}</strong>
                <span className="user-mgmt-modal-meta" dir="ltr">({startTargetUser.username})</span>
                {' · '}
                {getUserRoles(startTargetUser).map((r) => labelRoleFa(r, { includeCode: false })).join('، ')}
              </p>
              <p style={{ fontSize: '0.85rem', color: '#64748b', lineHeight: 1.7, marginBottom: '1rem' }}>
                فقط فرایندهای پرسنل‌محور اینجا هستند. آماده‌سازی ترم را از{' '}
                <Link to="/panel/semester-prep" style={{ fontWeight: 600 }}>هاب آماده‌سازی ترم</Link>
                {' '}شروع کنید.
              </p>
              {processDefinitions.length === 0 ? (
                <p className="muted" style={{ fontSize: '0.9rem' }}>
                  هیچ فرایند پرسنل‌محور فعالی برای شروع دستی یافت نشد.
                </p>
              ) : (
                <form onSubmit={handleStartProcess}>
                  <div className="form-group">
                    <label className="form-label">فرایند</label>
                    <select
                      className="form-input"
                      value={startForm.process_code}
                      onChange={(e) => setStartForm({ ...startForm, process_code: e.target.value })}
                      required
                    >
                      <option value="">انتخاب فرایند...</option>
                      {startProcessGroups.map((group) => (
                        <optgroup key={group.id} label={group.label}>
                          {group.items.map((p) => (
                            <option key={p.code} value={p.code}>
                              {p.name_fa} ({p.code})
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </div>
                  <button className="btn btn-primary" type="submit" style={{ marginTop: '1rem' }}>
                    شروع فرایند
                  </button>
                </form>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت کاربران</h1>
          <p className="page-subtitle">ایجاد و مدیریت حساب‌های کاربری | مجموع: {users.length} کاربر</p>
        </div>
        {isAdmin && (
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
            placeholder="جستجو: نام کاربری، نام، شماره دانشجویی یا کد ملی..."
          />
          <div className="user-mgmt-role-chips">
            <button type="button" className={`btn ${roleFilter === '' ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setRoleFilter('')}>همه</button>
            {rolesInUse.map((r) => (
              <button key={r} type="button" className={`btn ${roleFilter === r ? 'btn-primary' : 'btn-outline'} btn-sm`} onClick={() => setRoleFilter(r)}>
                {labelRoleFa(r, { includeCode: false })}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className={`card user-management-card${isResizingCol ? ' user-management-card-resizing' : ''}`}>
        <p className="user-mgmt-table-scroll-hint" dir="rtl">
          روی ناحیهٔ جدول اسکرول عمودی کنید؛ برای ستون «عملیات» اسکرول افقی هم لازم است. لبهٔ ستون‌ها را بکشید تا عرض عوض شود.
        </p>
        <div className="user-management-table-wrap">
          <table className="table-users" style={{ width: tableMinWidth, minWidth: tableMinWidth }}>
            <colgroup>
              {USER_TABLE_COLS.map((col) => (
                <col key={col.key} style={{ width: colWidths[col.key] || col.defaultWidth }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {USER_TABLE_COLS.map((col) => (
                  <th key={col.key} style={{ width: colWidths[col.key] || col.defaultWidth }}>
                    <span className="table-users-th-label">{col.label}</span>
                    <button
                      type="button"
                      className="table-users-col-resize"
                      aria-label={`تغییر عرض ستون ${col.label}`}
                      title="کشیدن برای تغییر عرض ستون"
                      onMouseDown={(e) => onColResizeStart(e, col.key)}
                    />
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={USER_TABLE_COLS.length} className="table-users-empty">در حال بارگذاری...</td></tr>
              ) : filteredUsers.length === 0 ? (
                <tr><td colSpan={USER_TABLE_COLS.length} className="table-users-empty">کاربری یافت نشد</td></tr>
              ) : (
                filteredUsers.map((u) => (
                  <tr key={u.id} className="table-users-row" style={{ opacity: u.is_active ? 1 : 0.55 }}>
                    <td className="table-users-cell table-users-cell-ellipsis" title={u.username}><strong>{u.username}</strong></td>
                    <td className="table-users-cell table-users-cell-ellipsis" title={u.full_name_fa || ''}>{u.full_name_fa || '-'}</td>
                    <td className="table-users-cell table-users-cell-role">
                      <div className="user-mgmt-role-chips">
                        {getUserRoles(u).map((r) => (
                          <span key={r} className="badge badge-primary badge-tight">
                            {labelRoleFa(r, { includeCode: false })}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="table-users-cell table-users-cell-ltr table-users-cell-ellipsis" title={u.student_code || ''}>
                      {u.student_code ? formatStudentCodeDisplay(u.student_code) : '-'}
                    </td>
                    <td className="table-users-cell table-users-cell-ltr table-users-cell-ellipsis" title={u.national_code || ''}>{u.national_code || '-'}</td>
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
                        {!getUserRoles(u).every((r) => r === 'student' || r === 'applicant') && (
                          <button
                            type="button"
                            className="btn btn-primary btn-xs"
                            onClick={() => openStartProcess(u)}
                            title="شروع فرایند پرسنل‌محور برای این کاربر"
                          >
                            شروع فرایند
                          </button>
                        )}
                        <button type="button" className="btn btn-outline btn-xs" onClick={() => openEditModal(u)}>ویرایش</button>
                        <button
                          type="button"
                          className="btn btn-outline btn-xs"
                          onClick={() => openSetPasswordModal(u)}
                          title="تنظیم رمز عبور برای ورود با نام کاربری"
                        >
                          رمز
                        </button>
                        {isAdmin && (
                          <>
                            <button
                              type="button"
                              className={`btn btn-xs ${u.is_active ? 'btn-danger' : 'btn-success'}`}
                              onClick={() => handleToggleActive(u)}
                              disabled={u.id === currentUser?.id}
                            >
                              {u.is_active ? 'غیرفعال' : 'فعال'}
                            </button>
                            <button
                              type="button"
                              className="btn btn-outline btn-xs"
                              style={{ borderColor: 'var(--danger, #b91c1c)', color: 'var(--danger, #b91c1c)' }}
                              onClick={() => setDeleteTarget(u)}
                              disabled={u.id === currentUser?.id}
                              title="حذف ردیف از پایگاه داده — برگشت‌ناپذیر"
                            >
                              حذف
                            </button>
                          </>
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
