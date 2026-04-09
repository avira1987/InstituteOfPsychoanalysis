import React, { useState, useEffect } from 'react'
import { processApi } from '../services/api'
import { resolveProcessSopOrder } from '../utils/processSopOrder'
import ProcessSopDocModal from '../components/ProcessSopDocModal'

export default function ProcessList() {
  const [processes, setProcesses] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [toast, setToast] = useState(null)
  const [viewSopProcessId, setViewSopProcessId] = useState(null)

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
      {viewSopProcessId && (
        <ProcessSopDocModal processId={viewSopProcessId} onClose={() => setViewSopProcessId(null)} />
      )}
      {toast && <div className={`toast toast-${toast.type}`}>{toast.msg}</div>}

      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت فرایندها</h1>
          <p className="page-subtitle">
            فقط مشاهدهٔ متن و تصویر SOP و تغییر وضعیت فعال/غیرفعال — بدون ایجاد یا ویرایش فرایند | مجموع:{' '}
            {processes.length} فرایند
          </p>
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th style={{ width: '4.5rem' }}>SOP</th>
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
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
              ) : processes.length === 0 ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>
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
                      </>
                    )}
                  </div>
                </td></tr>
              ) : (
                processes.map((p) => {
                  const sopN = resolveProcessSopOrder(p)
                  return (
                  <tr key={p.id} style={{ opacity: p.is_active ? 1 : 0.6 }}>
                    <td style={{ textAlign: 'center', fontWeight: 700, color: 'var(--text-secondary)' }}>
                      {sopN != null ? sopN : '—'}
                    </td>
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
                      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          className="btn btn-outline btn-sm"
                          onClick={() => setViewSopProcessId(p.id)}
                          title="متن و تصویر SOP ذخیره‌شده"
                        >
                          مشاهده
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
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
