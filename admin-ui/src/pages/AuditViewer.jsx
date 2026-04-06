import React, { useState, useEffect } from 'react'
import { auditApi } from '../services/api'
import { labelProcess, labelState, labelTriggerEvent } from '../utils/processDisplay'
import { buildAuditSummary, formatActorLine } from '../utils/auditDisplay'
import AuditDetailsHuman from '../components/AuditDetailsHuman'

const ACTION_FILTER_OPTIONS = [
  { value: '', label: 'همهٔ انواع' },
  { value: 'transition', label: 'جابه‌جایی بین مراحل' },
  { value: 'process_start', label: 'شروع فرایند جدید' },
  { value: 'process_updated', label: 'ویرایش تعریف فرایند' },
  { value: 'rule_change', label: 'تغییر قانون سیستم' },
  { value: 'sla_breach', label: 'نقض مهلت زمانی (SLA)' },
]

export default function AuditViewer() {
  const [logs, setLogs] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ action_type: '', process_code: '', limit: 50, offset: 0 })
  const [viewDetails, setViewDetails] = useState(null)
  const [showRawJson, setShowRawJson] = useState(false)

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
      case 'transition': return { label: 'جابه‌جایی مرحله', cls: 'badge-info' }
      case 'process_start': return { label: 'شروع فرایند', cls: 'badge-success' }
      case 'process_updated': return { label: 'ویرایش فرایند', cls: 'badge-warning' }
      case 'rule_change': return { label: 'تغییر قانون', cls: 'badge-warning' }
      case 'sla_breach': return { label: 'نقض مهلت', cls: 'badge-danger' }
      default: return { label: type || 'نامشخص', cls: 'badge-primary' }
    }
  }

  const currentPage = Math.floor(filters.offset / filters.limit) + 1
  const totalPages = Math.ceil(total / filters.limit)

  return (
    <div>
      {viewDetails && (
        <div className="modal-overlay" onClick={() => { setViewDetails(null); setShowRawJson(false) }}>
          <div className="modal modal-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>شرح رویداد</h3>
              <button type="button" className="modal-close" onClick={() => { setViewDetails(null); setShowRawJson(false) }}>&times;</button>
            </div>
            <div className="modal-body">
              <div
                style={{
                  padding: '1rem 1.1rem',
                  marginBottom: '1rem',
                  background: 'linear-gradient(145deg, var(--primary-light) 0%, var(--bg-white) 100%)',
                  borderRadius: 'var(--radius-lg)',
                  border: '1px solid var(--border)',
                  fontSize: '1rem',
                  lineHeight: 1.75,
                  color: 'var(--text)',
                }}
              >
                {buildAuditSummary(viewDetails)}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '0.85rem', marginBottom: '0.5rem' }}>
                <div className="detail-item">
                  <span className="detail-label">نوع رویداد</span>
                  <span className={`badge ${actionTypeLabel(viewDetails.action_type).cls}`}>{actionTypeLabel(viewDetails.action_type).label}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">فرایند</span>
                  <span style={{ fontWeight: 500 }}>{labelProcess(viewDetails.process_code)}</span>
                  {viewDetails.process_code && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', direction: 'ltr', textAlign: 'right', marginTop: '0.2rem' }}>
                      {viewDetails.process_code}
                    </div>
                  )}
                </div>
                {viewDetails.from_state && (
                  <div className="detail-item" style={{ gridColumn: '1 / -1' }}>
                    <span className="detail-label">تغییر مرحله</span>
                    <span>
                      از «{labelState(viewDetails.from_state)}» به «{labelState(viewDetails.to_state)}»
                    </span>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem', direction: 'ltr', textAlign: 'right' }}>
                      {viewDetails.from_state} → {viewDetails.to_state}
                    </div>
                  </div>
                )}
                <div className="detail-item">
                  <span className="detail-label">علت / رویداد سیستمی</span>
                  <span>{labelTriggerEvent(viewDetails.trigger_event)}</span>
                  {viewDetails.trigger_event && labelTriggerEvent(viewDetails.trigger_event) !== viewDetails.trigger_event && (
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', direction: 'ltr', textAlign: 'right', marginTop: '0.2rem' }}>
                      {viewDetails.trigger_event}
                    </div>
                  )}
                </div>
                <div className="detail-item">
                  <span className="detail-label">انجام‌دهنده</span>
                  <span>{formatActorLine(viewDetails)}</span>
                </div>
                <div className="detail-item">
                  <span className="detail-label">زمان ثبت</span>
                  <span>{viewDetails.timestamp ? new Date(viewDetails.timestamp).toLocaleString('fa-IR', { dateStyle: 'long', timeStyle: 'short' }) : '—'}</span>
                </div>
              </div>

              {viewDetails.details && <AuditDetailsHuman details={viewDetails.details} />}

              {viewDetails.details && Object.keys(viewDetails.details).length > 0 && (
                <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid var(--border)' }}>
                  <button
                    type="button"
                    className="btn btn-outline btn-sm"
                    onClick={() => setShowRawJson((v) => !v)}
                  >
                    {showRawJson ? 'پنهان کردن دادهٔ فنی خام' : 'نمایش دادهٔ فنی خام (JSON)'}
                  </button>
                  {showRawJson && (
                    <pre className="code-block" style={{ marginTop: '0.75rem', maxHeight: '240px', overflow: 'auto', fontSize: '0.78rem', direction: 'ltr', textAlign: 'left' }}>
                      {JSON.stringify(viewDetails.details, null, 2)}
                    </pre>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="page-header">
        <div>
          <h1 className="page-title">گزارش حسابرسی</h1>
          <p className="page-subtitle">تاریخچهٔ عملیات سیستم به زبان ساده — مجموع {total.toLocaleString('fa-IR')} مورد ثبت‌شده</p>
        </div>
      </div>

      <div className="card" style={{ marginBottom: '1.5rem', padding: '1rem 1.5rem' }}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div className="form-group" style={{ marginBottom: 0, flex: '1', minWidth: '180px' }}>
            <label className="form-label">نوع رویداد</label>
            <select
              className="form-input"
              value={filters.action_type}
              onChange={(e) => setFilters({ ...filters, action_type: e.target.value, offset: 0 })}
            >
              {ACTION_FILTER_OPTIONS.map((o) => (
                <option key={o.value || 'all'} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0, flex: '1', minWidth: '160px' }}>
            <label className="form-label">فیلتر با نام فنی فرایند</label>
            <input
              className="form-input"
              value={filters.process_code}
              onChange={(e) => setFilters({ ...filters, process_code: e.target.value, offset: 0 })}
              placeholder="مثلاً educational_leave"
              style={{ direction: 'ltr' }}
            />
            <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginTop: '0.35rem' }}>
              اختیاری؛ برای کاربران آشنا به کد فرایند در متادیتا
            </div>
          </div>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">تعداد در صفحه</label>
            <select
              className="form-input"
              value={filters.limit}
              onChange={(e) => setFilters({ ...filters, limit: parseInt(e.target.value, 10), offset: 0 })}
            >
              <option value="25">25</option>
              <option value="50">50</option>
              <option value="100">100</option>
            </select>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>زمان</th>
                <th>نوع</th>
                <th>فرایند</th>
                <th>جابه‌جایی مرحله</th>
                <th>رویداد</th>
                <th>انجام‌دهنده</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>در حال بارگذاری...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan="7" style={{ textAlign: 'center', padding: '2rem' }}>موردی یافت نشد</td></tr>
              ) : (
                logs.map((log) => {
                  const at = actionTypeLabel(log.action_type)
                  const transitionText = log.from_state && log.to_state
                    ? (
                      <span style={{ fontSize: '0.85rem', lineHeight: 1.5 }}>
                        <span style={{ display: 'block' }}>«{labelState(log.from_state)}» → «{labelState(log.to_state)}»</span>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', direction: 'ltr', display: 'block', textAlign: 'right' }}>
                          {log.from_state} → {log.to_state}
                        </span>
                      </span>
                    )
                    : '—'
                  return (
                    <tr key={log.id}>
                      <td style={{ whiteSpace: 'nowrap', fontSize: '0.82rem' }}>
                        {log.timestamp
                          ? new Date(log.timestamp).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })
                          : '—'}
                      </td>
                      <td><span className={`badge ${at.cls}`}>{at.label}</span></td>
                      <td>
                        <div style={{ fontWeight: 500, fontSize: '0.88rem' }}>{labelProcess(log.process_code)}</div>
                        {log.process_code && (
                          <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', direction: 'ltr', textAlign: 'right' }}>
                            {log.process_code}
                          </div>
                        )}
                      </td>
                      <td>{transitionText}</td>
                      <td style={{ fontSize: '0.85rem', maxWidth: '220px' }}>
                        <span style={{ display: 'block' }}>{labelTriggerEvent(log.trigger_event)}</span>
                        {log.trigger_event && labelTriggerEvent(log.trigger_event) !== log.trigger_event && (
                          <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', direction: 'ltr', display: 'block', textAlign: 'right' }}>
                            {log.trigger_event}
                          </span>
                        )}
                      </td>
                      <td style={{ fontSize: '0.82rem', maxWidth: '160px' }}>{formatActorLine(log)}</td>
                      <td>
                        <button type="button" className="btn btn-outline btn-sm" onClick={() => { setViewDetails(log); setShowRawJson(false) }}>
                          جزئیات
                        </button>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {totalPages > 1 && (
          <div className="pagination">
            <button
              type="button"
              className="btn btn-outline btn-sm"
              disabled={filters.offset === 0}
              onClick={() => setFilters({ ...filters, offset: Math.max(0, filters.offset - filters.limit) })}
            >
              قبلی
            </button>
            <span className="pagination-info">
              صفحه {currentPage.toLocaleString('fa-IR')} از {totalPages.toLocaleString('fa-IR')}
            </span>
            <button
              type="button"
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
