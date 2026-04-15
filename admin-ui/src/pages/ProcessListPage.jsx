import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { processApi } from '../services/api'

export default function ProcessListPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      setError(null)
      try {
        const res = await processApi.list()
        if (!cancelled) setRows(Array.isArray(res.data) ? res.data : [])
      } catch (err) {
        if (!cancelled) {
          const d = err.response?.data?.detail
          setError(typeof d === 'string' ? d : err.message || 'خطا در بارگذاری')
          setRows([])
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [])

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return rows
    return rows.filter((p) => {
      const fa = (p.name_fa || '').toLowerCase()
      const en = (p.name_en || '').toLowerCase()
      const code = (p.code || '').toLowerCase()
      return fa.includes(q) || en.includes(q) || code.includes(q)
    })
  }, [rows, filter])

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">مدیریت فرایندها</h1>
          <p className="page-subtitle">تعریف وضعیت‌ها، انتقال‌ها و مستندات هر فرایند</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1rem' }}>
        <div className="card-header">
          <h3 className="card-title" style={{ margin: 0 }}>فهرست فرایندها</h3>
        </div>
        <div style={{ padding: '1rem 1.25rem' }}>
          <label className="form-label" htmlFor="process-list-filter">جستجو</label>
          <input
            id="process-list-filter"
            className="form-input"
            type="search"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="نام یا کد فرایند..."
            autoComplete="off"
          />
        </div>
      </div>

      {error && (
        <div className="alert alert-danger" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div className="card">
        <div style={{ overflowX: 'auto' }}>
          {loading ? (
            <p style={{ padding: '1.5rem', color: 'var(--text-secondary)' }}>در حال بارگذاری...</p>
          ) : filtered.length === 0 ? (
            <p style={{ padding: '1.5rem', color: 'var(--text-secondary)' }}>
              {rows.length === 0 ? 'فرایندی ثبت نشده است.' : 'موردی با این جستجو یافت نشد.'}
            </p>
          ) : (
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr>
                  <th style={{ textAlign: 'right' }}>عنوان</th>
                  <th style={{ textAlign: 'right' }}>کد</th>
                  <th style={{ textAlign: 'right' }}>نسخه</th>
                  <th style={{ textAlign: 'right' }}>عملیات</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((p) => (
                  <tr key={p.id}>
                    <td style={{ fontWeight: 500 }}>{p.name_fa || '—'}</td>
                    <td><code style={{ fontSize: '0.85rem' }}>{p.code}</code></td>
                    <td>v{p.version ?? '—'}</td>
                    <td>
                      <Link className="btn btn-secondary btn-sm" to={`/panel/processes/${p.id}`}>
                        ویرایش / جزئیات
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
