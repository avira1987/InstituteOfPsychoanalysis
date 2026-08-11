import React, { useCallback, useEffect, useState } from 'react'
import { interviewerApi } from '../services/api'

export default function InterviewerPoolPanel({ showToast, onUpdated }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)
  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')
  const [editingId, setEditingId] = useState(null)
  const [editName, setEditName] = useState('')
  const [editEmail, setEditEmail] = useState('')
  const [editPhone, setEditPhone] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await interviewerApi.list()
      setRows(Array.isArray(res.data?.interviewers) ? res.data.interviewers : [])
    } catch {
      setRows([])
      showToast?.('خطا در بارگذاری مصاحبه‌کنندگان', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    load()
  }, [load])

  const notifyUpdated = async () => {
    await load()
    onUpdated?.()
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    const name = fullName.trim()
    if (!name) {
      showToast?.('نام فارسی را وارد کنید.', 'error')
      return
    }
    setBusy('create')
    try {
      await interviewerApi.create({
        full_name_fa: name,
        ...(username.trim() ? { username: username.trim() } : {}),
      })
      showToast?.('مصاحبه‌کننده اضافه شد.')
      setFullName('')
      setUsername('')
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در افزودن مصاحبه‌کننده', 'error')
    } finally {
      setBusy(null)
    }
  }

  const startEdit = (row) => {
    setEditingId(row.id)
    setEditName(row.full_name_fa || '')
    setEditEmail(row.email || '')
    setEditPhone(row.phone || '')
  }

  const cancelEdit = () => {
    setEditingId(null)
    setEditName('')
    setEditEmail('')
    setEditPhone('')
  }

  const saveEdit = async () => {
    if (!editingId) return
    const name = editName.trim()
    if (!name) {
      showToast?.('نام فارسی را وارد کنید.', 'error')
      return
    }
    setBusy(`edit:${editingId}`)
    try {
      await interviewerApi.update(editingId, {
        full_name_fa: name,
        email: editEmail.trim() || null,
        phone: editPhone.trim() || null,
      })
      showToast?.('مصاحبه‌کننده به‌روز شد.')
      cancelEdit()
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ویرایش مصاحبه‌کننده', 'error')
    } finally {
      setBusy(null)
    }
  }

  const removeRow = async (row) => {
    const label = row.full_name_fa || row.username || 'این مصاحبه‌گر'
    if (!window.confirm(`«${label}» از استخر مصاحبه‌کنندگان حذف (غیرفعال) شود؟`)) return
    setBusy(`del:${row.id}`)
    try {
      await interviewerApi.remove(row.id)
      showToast?.('مصاحبه‌کننده از استخر حذف شد.')
      if (editingId === row.id) cancelEdit()
      await notifyUpdated()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در حذف مصاحبه‌کننده', 'error')
    } finally {
      setBusy(null)
    }
  }

  return (
    <section id="interviewers" data-testid="interviewer-pool-panel">
      <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.35rem' }}>استخر مصاحبه‌کنندگان</h3>
      <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
        مصاحبه‌گران فعال در مرحلهٔ «تعیین مصاحبه‌کنندگان» فرایند آماده‌سازی ترم قابل انتخاب هستند.
        می‌توانید مصاحبه‌گر را اضافه، ویرایش یا از استخر حذف کنید.
      </p>

      <form
        onSubmit={handleCreate}
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.65rem',
          alignItems: 'flex-end',
          marginBottom: '1rem',
        }}
      >
        <label style={{ fontSize: '0.85rem', flex: '1 1 200px' }}>
          نام فارسی
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            placeholder="مثلاً دکتر رضایی"
            style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
            data-testid="interviewer-pool-name"
          />
        </label>
        <label style={{ fontSize: '0.85rem', flex: '1 1 180px' }}>
          نام کاربری (اختیاری)
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="خودکار ساخته می‌شود"
            style={{ display: 'block', width: '100%', marginTop: '0.25rem' }}
            data-testid="interviewer-pool-username"
          />
        </label>
        <button type="submit" className="btn btn-primary" disabled={busy === 'create'}>
          {busy === 'create' ? '…' : 'افزودن مصاحبه‌گر'}
        </button>
      </form>

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : rows.length === 0 ? (
        <p className="muted" style={{ margin: 0, fontSize: '0.88rem' }}>
          هنوز مصاحبه‌کننده‌ای ثبت نشده است.
        </p>
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="data-table" style={{ fontSize: '0.85rem', width: '100%' }}>
            <thead>
              <tr>
                <th>نام</th>
                <th>نام کاربری</th>
                <th>ایمیل</th>
                <th>تلفن</th>
                <th style={{ width: 160 }}>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const isEditing = editingId === row.id
                return (
                  <tr key={row.id} data-testid={`interviewer-pool-row-${row.id}`}>
                    <td>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editName}
                          onChange={(e) => setEditName(e.target.value)}
                          style={{ width: '100%', minWidth: 120 }}
                          data-testid="interviewer-pool-edit-name"
                        />
                      ) : (
                        row.full_name_fa || '—'
                      )}
                    </td>
                    <td>{row.username}</td>
                    <td>
                      {isEditing ? (
                        <input
                          type="email"
                          value={editEmail}
                          onChange={(e) => setEditEmail(e.target.value)}
                          style={{ width: '100%', minWidth: 140 }}
                          data-testid="interviewer-pool-edit-email"
                        />
                      ) : (
                        row.email || '—'
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <input
                          type="text"
                          value={editPhone}
                          onChange={(e) => setEditPhone(e.target.value)}
                          style={{ width: '100%', minWidth: 110 }}
                          data-testid="interviewer-pool-edit-phone"
                        />
                      ) : (
                        row.phone || '—'
                      )}
                    </td>
                    <td>
                      {isEditing ? (
                        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={busy === `edit:${row.id}`}
                            onClick={saveEdit}
                            data-testid={`interviewer-pool-save-${row.id}`}
                          >
                            ذخیره
                          </button>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={cancelEdit}
                          >
                            انصراف
                          </button>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            onClick={() => startEdit(row)}
                            data-testid={`interviewer-pool-edit-${row.id}`}
                          >
                            ویرایش
                          </button>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            disabled={busy === `del:${row.id}`}
                            onClick={() => removeRow(row)}
                            data-testid={`interviewer-pool-delete-${row.id}`}
                          >
                            حذف
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
