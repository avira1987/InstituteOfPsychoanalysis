import React, { useState, useEffect, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { panelApi } from '../services/api'
import { getOperatorFollowupDestination } from '../utils/operatorFollowupDeepLinks'

function groupByRole(items) {
  const m = new Map()
  for (const it of items) {
    const key = it.responsible_role_label_fa || 'سایر'
    if (!m.has(key)) m.set(key, [])
    m.get(key).push(it)
  }
  return m
}

export default function PrimaryAdminOperatorFollowup() {
  const [data, setData] = useState(null)
  const [err, setErr] = useState(null)
  const [loading, setLoading] = useState(true)
  const [includeGaps, setIncludeGaps] = useState(false)
  const [gapOpen, setGapOpen] = useState(false)
  const [refreshToken, setRefreshToken] = useState(0)

  const load = useCallback(() => {
    /** بدون فیلتر دانشجو: همهٔ موارد از دیتابیس به‌صورت خودکار پیدا و در صندوق ادغام می‌شود */
    const params = {
      include_reference: false,
      include_gaps: includeGaps,
      gap_limit: 100,
      process_limit: 200,
      assignment_limit: 100,
      scan_cap: 2500,
    }
    return panelApi.operatorFollowupInbox(params)
  }, [includeGaps])

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setErr(null)
    load()
      .then((r) => {
        if (!cancelled) setData(r.data)
      })
      .catch((e) => {
        if (!cancelled) {
          const d = e.response?.data?.detail
          setErr(typeof d === 'string' ? d : e.message || 'خطا')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [load, refreshToken])

  const grouped = useMemo(() => {
    const items = data?.items || []
    return groupByRole(items)
  }, [data])

  if (loading) {
    return (
      <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="primary-admin-followup-loading">
        <div className="card-header">
          <h3 className="card-title">صندوق پیگیری اپراتورها</h3>
        </div>
        <p style={{ padding: '1rem', color: 'var(--text-secondary)', margin: 0 }}>در حال بارگذاری…</p>
      </div>
    )
  }

  if (err) {
    return (
      <div className="card alert alert-danger" style={{ marginBottom: '1.5rem' }} data-testid="primary-admin-followup-error">
        <div className="card-header">
          <h3 className="card-title">صندوق پیگیری اپراتورها</h3>
        </div>
        <p style={{ padding: '1rem', margin: 0 }}>{err}</p>
      </div>
    )
  }

  const items = data?.items || []
  const summary = data?.summary
  const gapItems = data?.gap_items || []
  const readinessAlerts = data?.readiness_alerts || []

  return (
    <div
      className="card"
      style={{ marginBottom: '1.5rem', borderColor: 'var(--primary-light, #dbeafe)' }}
      data-testid="primary-admin-operator-followup"
    >
      <div className="card-header">
        <div>
          <h3 className="card-title">صندوق پیگیری اپراتورها</h3>
          <p className="card-subtitle" style={{ marginTop: '0.35rem' }}>
            این لیست از روی فرایندهای باز (نیازمند نقش اپراتور) و تکلیف‌های ارسال‌شدهٔ بدون نمره{' '}
            <strong>به‌صورت خودکار</strong> ساخته می‌شود؛ نیازی به جستجو یا فیلتر دستی نیست. جزئیات نقش‌ها در{' '}
            <Link to="/panel/guide">راهنمای جامع</Link>.
          </p>
        </div>
        {summary && (
          <span className="badge badge-primary">
            فرایند: {summary.process_count?.toLocaleString('fa-IR') || 0} · تکلیف:{' '}
            {summary.assignment_count?.toLocaleString('fa-IR') || 0}
            {typeof summary.scan_cap === 'number' && (
              <>
                {' '}
                · اسکن تا {summary.scan_cap.toLocaleString('fa-IR')} ردیف
              </>
            )}
            {includeGaps && ` · کمبود: ${(summary.gap_count ?? gapItems.length)?.toLocaleString('fa-IR') || 0}`}
            {typeof summary.readiness_count === 'number' && summary.readiness_count > 0 && (
              <>
                {' '}
                · آمادگی نقش: {summary.readiness_count.toLocaleString('fa-IR')}
              </>
            )}
          </span>
        )}
      </div>

      <div
        style={{
          padding: '0.75rem 1rem',
          borderBottom: '1px solid var(--border)',
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.75rem',
          alignItems: 'center',
        }}
      >
        <button type="button" className="btn btn-outline btn-sm" onClick={() => setRefreshToken((t) => t + 1)}>
          به‌روزرسانی لیست
        </button>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
          <input type="checkbox" checked={includeGaps} onChange={(e) => setIncludeGaps(e.target.checked)} />
          بررسی کمبود (قواعد اضافی)
        </label>
      </div>

      {includeGaps && gapItems.length > 0 && (
        <div style={{ borderBottom: '1px solid var(--border)' }}>
          <button
            type="button"
            onClick={() => setGapOpen(!gapOpen)}
            className="btn btn-ghost"
            style={{ width: '100%', textAlign: 'right', padding: '0.75rem 1rem', fontWeight: 600 }}
          >
            {gapOpen ? '▼' : '◀'} موارد کمبود ({gapItems.length.toLocaleString('fa-IR')})
          </button>
          {gapOpen && (
            <ul className="operator-followup-list" style={{ padding: '0 1rem 1rem' }}>
              {gapItems.map((g) => (
                <li key={`${g.rule_id}-${g.student_id}`}>
                  <Link
                    className="operator-followup-row-link"
                    to={`/panel/students?student_id=${encodeURIComponent(g.student_id)}`}
                    title="ردیابی دانشجو"
                  >
                    <span className="operator-followup-title">{g.title_fa}</span>
                    <span className="operator-followup-meta">
                      {' '}
                      — {g.student_code} — {g.process_code}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {includeGaps && gapItems.length === 0 && (
        <p style={{ padding: '0.75rem 1rem', color: 'var(--text-secondary)', fontSize: '0.9rem', margin: 0 }}>
          قانون کمبودی فعال نیست یا موردی یافت نشد.
        </p>
      )}

      {readinessAlerts.length > 0 && (
        <div style={{ borderBottom: '1px solid var(--border)', padding: '0.75rem 1rem 1rem' }}>
          <h4 style={{ fontSize: '0.95rem', marginBottom: '0.65rem', color: 'var(--text-secondary)' }}>
            هشدار آمادگی اپراتورها (همهٔ نقش‌ها)
          </h4>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0, display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {readinessAlerts.map((a) => (
              <li
                key={a.id || a.title_fa}
                style={{
                  padding: '0.65rem 0.85rem',
                  borderRadius: '8px',
                  border: '1px solid #fbbf24',
                  background: '#fffbeb',
                  fontSize: '0.88rem',
                }}
              >
                <strong style={{ display: 'block', marginBottom: '0.25rem' }}>{a.title_fa}</strong>
                {a.detail_fa && <span style={{ color: 'var(--text-secondary)' }}>{a.detail_fa}</span>}
                {a.action_href && a.action_label_fa && (
                  <div style={{ marginTop: '0.45rem' }}>
                    <Link className="btn btn-sm btn-primary" to={a.action_href}>
                      {a.action_label_fa}
                    </Link>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {items.length === 0 && readinessAlerts.length === 0 ? (
        <div className="empty-state" style={{ padding: '1.5rem' }}>
          <div style={{ fontSize: '2rem', marginBottom: '0.5rem' }}>📭</div>
          <p style={{ margin: '0 0 0.75rem', color: 'var(--text-secondary)' }}>
            موردی در بک‌لاگ اپراتور، تکلیف بدون نمره، یا هشدار آمادگی ثبت نشده است.
          </p>
          <p style={{ margin: 0, fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
            اگر انتظار پروندهٔ باز دارید: از{' '}
            <Link to="/panel/students">ردیابی دانشجو</Link> یا{' '}
            <Link to="/panel/processes">مدیریت فرایندها</Link> وضعیت نمونه‌ها را بررسی کنید؛ ممکن است مرحله به
            نقش دانشجو مانده باشد یا دادهٔ مرحله در دیتابیس با فرایند هم‌خوان نباشد.
          </p>
        </div>
      ) : items.length === 0 ? (
        <div className="empty-state" style={{ padding: '1rem 1.5rem 1.5rem' }}>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            در این بخش فقط نمونه‌های فرایند با نقش اپراتور (غیر دانشجو) فهرست می‌شود؛ در صورت نیاز بالا را برای هشدارهای آمادگی ببینید.
          </p>
        </div>
      ) : (
        <div style={{ padding: '0 1rem 1.25rem' }}>
          {[...grouped.entries()].map(([roleLabel, rows]) => (
            <div key={roleLabel} style={{ marginTop: '1rem' }}>
              <h4 style={{ fontSize: '0.95rem', marginBottom: '0.5rem', color: 'var(--text-secondary)' }}>{roleLabel}</h4>
              <ul className="operator-followup-list">
                {rows.map((it, idx) => {
                  const dest = getOperatorFollowupDestination(it)
                  return (
                    <li key={`${it.kind}-${it.instance_id || it.assignment_id}-${idx}`}>
                      <Link className="operator-followup-row-link" to={dest.href} title={dest.hintFa}>
                        {it.kind === 'process' && (
                          <>
                            <span className="operator-followup-title">{it.process_name_fa}</span>
                            <span className="operator-followup-meta">
                              {' '}
                              دانشجو <strong>{it.student_code}</strong>
                              {' — '}
                              {it.state_name_fa}
                              {it.inferred && (
                                <span className="badge badge-outline" style={{ marginRight: '0.35rem', fontSize: '0.7rem' }}>
                                  تخمین
                                </span>
                              )}
                              {it.uncertain && (
                                <span className="badge badge-warning" style={{ marginRight: '0.35rem', fontSize: '0.7rem' }}>
                                  نیاز به بررسی
                                </span>
                              )}
                            </span>
                          </>
                        )}
                        {it.kind === 'assignment_grading' && (
                          <>
                            <span className="operator-followup-title">تصحیح تکلیف: {it.title_fa}</span>
                            <span className="operator-followup-meta">
                              {' '}
                              — دانشجو <strong>{it.student_code}</strong>
                            </span>
                          </>
                        )}
                      </Link>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
