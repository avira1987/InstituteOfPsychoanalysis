import React, { useCallback, useEffect, useState } from 'react'
import { interviewerApi } from '../services/api'

export default function InterviewerPoolPanel({ showToast, onUpdated }) {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [fullName, setFullName] = useState('')
  const [username, setUsername] = useState('')

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

  const handleCreate = async (e) => {
    e.preventDefault()
    const name = fullName.trim()
    if (!name) {
      showToast?.('نام فارسی را وارد کنید.', 'error')
      return
    }
    setSaving(true)
    try {
      await interviewerApi.create({
        full_name_fa: name,
        ...(username.trim() ? { username: username.trim() } : {}),
      })
      showToast?.('مصاحبه‌کننده اضافه شد.')
      setFullName('')
      setUsername('')
      await load()
      onUpdated?.()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در افزودن مصاحبه‌کننده', 'error')
    } finally {
      setSaving(false)
    }
  }

  return (
    <section id="interviewers" data-testid="interviewer-pool-panel">
      <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.35rem' }}>استخر مصاحبه‌کنندگان</h3>
      <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
        مصاحبه‌گران فعال در مرحلهٔ «تعیین مصاحبه‌کنندگان» فرایند آماده‌سازی ترم قابل انتخاب هستند.
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
          />
        </label>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? '…' : 'افزودن مصاحبه‌گر'}
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
          <table className="data-table" style={{ fontSize: '0.85rem' }}>
            <thead>
              <tr>
                <th>نام</th>
                <th>نام کاربری</th>
                <th>ایمیل</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td>{row.full_name_fa || '—'}</td>
                  <td>{row.username}</td>
                  <td>{row.email || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
