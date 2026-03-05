import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { processApi } from '../services/api'

export default function ProcessList() {
  const navigate = useNavigate()
  const [processes, setProcesses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [showCreate, setShowCreate] = useState(false)
  const [toast, setToast] = useState(null)
  const [form, setForm] = useState({ code: '', name_fa: '', name_en: '', initial_state_code: '', description: '' })

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 3000)
  }

  useEffect(() => {
    loadProcesses()
  }, [])

  const loadProcesses = async () => {
    setError(null)
    try {
      const res = await processApi.list()
      setProcesses(Array.isArray(res.data) ? res.data : [])
    } catch (err) {
      console.error('Failed to load processes:', err)
      const status = err.response?.status
      const detail = err.response?.data?.detail
      const isNetworkErr = err.code === 'ERR_NETWORK' || !err.response
      let msg = 'خطا در بارگذاری فرایندها'
      if (isNetworkErr) msg = 'خطای شبکه (Mixed Content یا قطع اتصال) - صفحه را رفرش کنید'
      else if (status === 401) msg = 'لطفاً دوباره وارد شوید (ورود مجدد)'
      else if (status === 403) msg = 'دسترسی غیرمجاز - نقش کاربری شما اجازه دسترسی ندارد'
      else if (status === 404) msg = 'آدرس API یافت نشد - احتمالاً ProxyPass تنظیم نشده'
      else if (status === 500) msg = 'خطای سرور: ' + (typeof detail === 'string' ? detail : JSON.stringify(detail || ''))
      else if (detail && typeof detail === 'string') msg += ': ' + detail
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async (e) => {
    e.preventDefault()
    try {
      const res = await processApi.create(form)
      showToast('فرایند جدید با موفقیت ایجاد شد')
      setShowCreate(false)
      setForm({ code: '', name_fa: '', name_en: '', initial_state_code: '', description: '' })
      loadProcesses()
      // Navigate to editor
      navigate(`/panel/processes/${res.data.id}`)
    } catch (err) {
      const isNetworkErr = err.code === 'ERR_NETWORK' || !err.response
      let msg = 'خطای نامشخص'
      if (isNetworkErr) {
        msg = 'خطای شبکه - درخواست مسدود شد (Mixed Content یا قطع اتصال)'
      } else {
        const d = err.response?.data?.detail
        if (err.response?.status === 401) msg = 'لطفاً دوباره وارد شوید'
        else if (err.response?.status === 403) msg = 'دسترسی غیرمجاز - نقش کاربری شما اجازه ایجاد فرایند ندارد'
        else if (err.response?.status === 404) msg = 'آدرس API یافت نشد - ProxyPass یا مسیر بک‌اند را بررسی کنید'
        else if (Array.isArray(d)) msg = d.map((e) => e?.msg || JSON.stringify(e)).join('؛ ')
        else if (typeof d === 'string') msg = d
        else if (d) msg = JSON.stringify(d)
        else msg = err.message || 'خطا در ارتباط با سرور'
      }
      showToast('خطا در ایجاد فرایند: ' + msg, 'error')
    }
  }

  const handleToggleActive = async (process) => {
    try {
      if (process.is_active) {
        await processApi.delete(process.id)
        showToast(`فرایند '${process.name_fa}' غیرفعال شد`)
      } else {
        await processApi.update(process.id, { is_active: true })
        showToast(`فرایند '${process.name_fa}' فعال شد`)
      }
      loadProcesses()
    } catch (err) {
      showToast('خطا', 'error')
    }
  }

  return (
    <div>
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت فرایندها</h1>
          <p className="page-subtitle">تعریف و ویرایش فرایندهای ماشین حالت | مجموع: {processes.length} فرایند</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          {showCreate ? 'لغو' : '+ فرایند جدید'}
        </button>
      </div>

      {showCreate && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3 className="card-title" style={{ marginBottom: '1rem' }}>ایجاد فرایند جدید</h3>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label className="form-label">کد فرایند (انگلیسی) *</label>
              <input className="form-input" value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required placeholder="مثلاً educational_leave" style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group">
              <label className="form-label">نام فارسی *</label>
              <input className="form-input" value={form.name_fa} onChange={(e) => setForm({ ...form, name_fa: e.target.value })} required placeholder="مثلاً مرخصی آموزشی موقت" />
            </div>
            <div className="form-group">
              <label className="form-label">نام انگلیسی</label>
              <input className="form-input" value={form.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} placeholder="مثلاً Educational Leave" style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group">
              <label className="form-label">کد وضعیت اولیه *</label>
              <input className="form-input" value={form.initial_state_code} onChange={(e) => setForm({ ...form, initial_state_code: e.target.value })} required placeholder="مثلاً request_form" style={{ direction: 'ltr' }} />
            </div>
            <div className="form-group" style={{ gridColumn: '1 / -1' }}>
              <label className="form-label">توضیحات</label>
              <textarea className="form-input" rows="2" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="شرح مختصر هدف فرایند" />
            </div>
            <div style={{ gridColumn: '1 / -1' }}>
              <button className="btn btn-primary" type="submit">ایجاد و ورود به ویرایشگر</button>
            </div>
          </form>
        </div>
      )}

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>کد</th>
                <th>نام فارسی</th>
                <th>نسخه</th>
                <th>وضعیت اولیه</th>
                <th>وضعیت</th>
                <th>عملیات</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
              ) : processes.length === 0 ? (
                <tr><td colSpan="6" style={{ textAlign: 'center', padding: '2rem' }}>
                  <div className="empty-state">
                    {error ? (
                      <>
                        <div className="empty-state-icon">⚠️</div>
                        <p style={{ color: 'var(--danger)' }}>{error}</p>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>آدرس API: /anistito/api/admin/processes/</p>
                        <button className="btn btn-outline" onClick={loadProcesses} style={{ marginTop: '0.5rem' }}>تلاش مجدد</button>
                      </>
                    ) : (
                      <>
                        <div className="empty-state-icon">⚙️</div>
                        <p>فرایندی تعریف نشده است</p>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-light)' }}>برای شروع، روی «+ فرایند جدید» کلیک کنید</p>
                      </>
                    )}
                  </div>
                </td></tr>
              ) : (
                processes.map((p) => (
                  <tr key={p.id} style={{ opacity: p.is_active ? 1 : 0.6 }}>
                    <td><span className="badge badge-primary">{p.code}</span></td>
                    <td>
                      <div>
                        <strong>{p.name_fa}</strong>
                        {p.description && (
                          <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.15rem' }}>
                            {p.description.length > 60 ? p.description.substring(0, 60) + '...' : p.description}
                          </div>
                        )}
                      </div>
                    </td>
                    <td>v{p.version}</td>
                    <td><code>{p.initial_state_code}</code></td>
                    <td>
                      <span className={`badge ${p.is_active ? 'badge-success' : 'badge-danger'}`}>
                        {p.is_active ? 'فعال' : 'غیرفعال'}
                      </span>
                    </td>
                    <td>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-outline btn-sm" onClick={() => navigate(`/panel/processes/${p.id}`)}>
                          ویرایش
                        </button>
                        <button
                          className={`btn btn-sm ${p.is_active ? 'btn-danger' : 'btn-success'}`}
                          onClick={() => handleToggleActive(p)}
                        >
                          {p.is_active ? 'غیرفعال' : 'فعال'}
                        </button>
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
