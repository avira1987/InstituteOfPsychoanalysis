import React, { useState, useEffect } from 'react'
import { auditApi } from '../services/api'

export default function AuditViewer() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ action_type: '', process_code: '', limit: 50, offset: 0 })
  const [viewDetails, setViewDetails] = useState(null)

  useEffect(() => {
    loadLogs()
  }, [filters])

  const loadLogs = async () => {
    setLoading(true)
    try {
      const params = {}
      if (filters.action_type) params.action_type = filters.action_type
      if (filters.process_code) params.process_code = filters.process_code
      params.limit = filters.limit
      params.offset = filters.offset

      const res = await auditApi.list(params)
      setLogs(res.data.logs || [])
      setTotal(res.data.total || 0)
    } catch (err) {
      console.error('Failed to load audit logs:', err)
    } finally {
      setLoading(false)
    }
  }

  const actionTypeLabel = (type) => {
    switch (type) {
      case 'transition': return { label: 'انتقال', cls: 'badge-info' }
      case 'process_start': return { label: 'شروع فرایند', cls: 'badge-success' }
      case 'process_updated': return { label: 'ویرایش فرایند', cls: 'badge-warning' }
      case 'rule_change': return { label: 'تغییر قانون', cls: 'badge-warning' }
      case 'sla_breach': return { label: 'نقض SLA', cls: 'badge-danger' }
      default: return { label: type, cls: 'badge-primary' }
    }
  }

  const currentPage = Math.floor(filters.offset / filters.limit) + 1
  const totalPages = Math.ceil(total / filters.limit)

  return (
    <div>
      {/* Details Modal */}
      {viewDetails && (
        <div className="modal-overlay" onClick={() => setViewDetails(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>جزئیات لاگ</h3>
              <button className="modal-close" onClick={() => setViewDetails(null)}>&times;</button>
            </div>
            <div className="modal-body">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem', marginBottom: '1rem' }}>
                <div className="detail-item">
                  <span className="detail-label">نوع:</span>
                  <span className={`badge ${actionTypeLabel(viewDetails.action_type).cls}`}>{actionTypeLabel(viewDetails.action_type).label}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">فرایند:</span>
                  <span>{viewDetails.process_code || '-'}</span>
                </div>
                {viewDetails.from_state && (
                  <div className="detail-item">
                    <span className="detail-label">انتقال:</span>
                    <span>{viewDetails.from_state} → {viewDetails.to_state}</span>
                  </div>
                )}
                <div className="detail-item">
                  <span className="detail-label">رویداد:</span>
                  <span>{viewDetails.trigger_event || '-'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">بازیگر:</span>
                  <span>{viewDetails.actor_name || viewDetails.actor_role || '-'}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">زمان:</span>
                  <span>{new Date(viewDetails.timestamp).toLocaleString('fa-IR')}</span>
                </div>
              </div>
              {viewDetails.details && (
                <>
                  <h4 style={{ marginBottom: '0.5rem' }}>جزئیات فنی:</h4>
                  <pre className="code-block">{JSON.stringify(viewDetails.details, null, 2)}</pre>
                </>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">گزارش حسابرسی (Audit Log)</h1>
          <p className="page-subtitle">تاریخچه کامل تغییرات و عملیات سیستم | مجموع: {total} رکورد</p>
        </div>
      </div>

      {/* Filters */}
      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ marginBottom: 0, flex: '1', minWidth: '150px' }}>
            <label className="form-label">نوع عملیات</label>
            <select className="form-input" value={filters.action_type}
              onChange={(e) => setFilters({ ...filters, action_type: e.target.value, offset: 0 })}>
              <option value="">همه</option>
              <option value="transition">انتقال</option>
              <option value="process_start">شروع فرایند</option>
              <option value="process_updated">ویرایش فرایند</option>
              <option value="rule_change">تغییر قانون</option>
              <option value="sla_breach">نقض SLA</option>
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0, flex: '1', minWidth: '150px' }}>
            <label className="form-label">کد فرایند</label>
            <input className="form-input" value={filters.process_code}
              onChange={(e) => setFilters({ ...filters, process_code: e.target.value, offset: 0 })}
              placeholder="مثلاً educational_leave" style={{ direction: 'ltr' }} />
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">تعداد در صفحه</label>
            <select className="form-input" value={filters.limit}
              onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value), offset: 0 })}>
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
        </div>
      </div>

      {/* Logs Table */}
      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>زمان</th>
                <th>نوع</th>
                <th>فرایند</th>
                <th>انتقال</th>
                <th>رویداد</th>
                <th>بازیگر</th>
                <th>جزئیات</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>لاگی یافت نشد</td></tr>
              ) : (
                logs.map((log) => {
                  const at = actionTypeLabel(log.action_type)
                  return (
                    <tr key={log.id}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: '0.8rem' }}>
                        {new Date(log.timestamp).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })}
                      </td>
                      <td><span className={`badge ${at.cls}`}>{at.label}</span></td>
                      <td>{log.process_code || '-'}</td>
                      <td>
                        {log.from_state && log.to_state ? (
                          <span style={{ fontSize: '0.8rem' }}>
                            {log.from_state} → {log.to_state}
                          </span>
                        ) : '-'}
                      </td>
                      <td style={{ fontSize: '0.85rem' }}>{log.trigger_event || '-'}</td>
                      <td>
                        <span style={{ fontSize: '0.8rem' }}>
                          {log.actor_name || log.actor_role || '-'}
                        </span>
                      </td>
                      <td>
                        <button className="btn btn-outline btn-sm" onClick={() => setViewDetails(log)}>
                          مشاهده
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="pagination">
            <button
              className="btn btn-outline btn-sm"
              disabled={filters.offset === 0}
              onClick={() => setFilters({ ...filters, offset: Math.max(0, filters.offset - filters.limit) })}
            >
              قبلی
            </button>
            <span className="pagination-info">
              صفحه {currentPage} از {totalPages}
            </span>
            <button
              className="btn btn-outline btn-sm"
              disabled={filters.offset + filters.limit >= total}
              onClick={() => setFilters({ ...filters, offset: filters.offset + filters.limit })}
            >
              بعدی
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
