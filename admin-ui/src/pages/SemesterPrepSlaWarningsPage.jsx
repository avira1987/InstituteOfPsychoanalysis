import React, { useCallback, useEffect, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { semesterPrepApi, schedulerApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { labelRoleFa } from '../utils/roleLabels'

const PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی ترم پاییز',
  winter_semester_preparation: 'آماده‌سازی ترم زمستان',
}

export default function SemesterPrepSlaWarningsPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [status, setStatus] = useState(null)
  const [warnings, setWarnings] = useState(null)
  const [loading, setLoading] = useState(true)
  const { showToast } = useToast()
  const [running, setRunning] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [statusRes, warnRes] = await Promise.all([
        semesterPrepApi.getStatus(),
        semesterPrepApi.getSlaWarnings(),
      ])
      setStatus(statusRes.data)
      setWarnings(warnRes.data)
    } catch (e) {
      showToast('خطا در بارگذاری هشدارهای مهلت', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const runCheck = async () => {
    setRunning(true)
    try {
      await schedulerApi.runPass()
      showToast('دور بررسی مهلت‌ها اجرا شد. در حال بازخوانی…')
      await load()
    } catch (e) {
      showToast('خطا در اجرای بررسی مهلت‌ها', 'error')
    } finally {
      setRunning(false)
    }
  }

  const processes = status?.processes || {}
  const rows = warnings?.warnings || []

  return (
    <div className="page-container" style={{ maxWidth: 1000, margin: '0 auto', padding: '1.25rem' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: '1.35rem', marginBottom: '0.35rem' }}>هشدارهای مهلت آماده‌سازی ترم</h1>
          <p className="muted" style={{ marginBottom: '1rem', lineHeight: 1.7, maxWidth: 720 }}>
            در این فرایند مهلت‌ها فقط هشدار مدیریتی ایجاد می‌کنند و سیستم را قفل نمی‌کنند. این صفحه نشان می‌دهد
            پس از گذشتن مهلت هر مرحله، چه هشداری و برای چه گیرنده‌ای (از جمله <strong>مدیر آموزش</strong>) ارسال شده است.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <button type="button" className="btn btn-secondary" onClick={load} disabled={loading || running}>
            بازخوانی
          </button>
          {isAdmin && (
            <button type="button" className="btn btn-primary" onClick={runCheck} disabled={running}>
              {running ? 'در حال اجرا…' : 'اجرای دستی بررسی مهلت‌ها'}
            </button>
          )}
        </div>
      </div>

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <>
          <section style={{ marginBottom: '1.5rem' }}>
            <h2 style={{ fontSize: '1.05rem', margin: '0 0 0.6rem' }}>وضعیت مهلت مرحله فعلی</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {['fall_semester_preparation', 'winter_semester_preparation'].map((code) => {
                const entry = processes[code] || {}
                if (!entry.active) return null
                const recipients = entry.sla_warning_recipients_fa || []
                return (
                  <div
                    key={code}
                    style={{
                      border: '1px solid #e2e8f0',
                      borderRadius: '10px',
                      padding: '0.9rem 1.1rem',
                      background: entry.sla_overdue ? '#fef2f2' : '#f8fafc',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                      <div>
                        <strong>{PROCESS_LABELS[code]}</strong> — مرحله: {entry.state_name_fa || entry.current_state}
                        {entry.sla_overdue ? (
                          <span style={{ color: '#b91c1c', marginRight: '0.5rem' }}>(مهلت گذشته)</span>
                        ) : (
                          <span style={{ color: '#15803d', marginRight: '0.5rem' }}>(در مهلت)</span>
                        )}
                      </div>
                      {entry.sla_deadline_at ? (
                        <div style={{ fontSize: '0.85rem', color: '#475569' }}>
                          مهلت: {formatShamsiTehran(entry.sla_deadline_at)}
                        </div>
                      ) : null}
                    </div>
                    <div style={{ fontSize: '0.85rem', color: '#475569', marginTop: '0.4rem' }}>
                      گیرندگان هشدار این مرحله: {recipients.length ? recipients.join('، ') : '—'}
                    </div>
                  </div>
                )
              })}
              {!processes.fall_semester_preparation?.active && !processes.winter_semester_preparation?.active && (
                <p className="muted">هیچ فرایند آماده‌سازی فعالی وجود ندارد.</p>
              )}
            </div>
          </section>

          <section>
            <h2 style={{ fontSize: '1.05rem', margin: '0 0 0.6rem' }}>
              هشدارهای ارسال‌شده ({warnings?.count || 0})
            </h2>
            {rows.length === 0 ? (
              <p className="muted">
                تاکنون هیچ هشدار مهلتی ثبت نشده است. اگر مهلت مرحله‌ای گذشته باشد، با اجرای «بررسی مهلت‌ها»
                هشدار ساخته و اینجا نمایش داده می‌شود.
              </p>
            ) : (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.88rem' }}>
                  <thead>
                    <tr style={{ background: '#f1f5f9', textAlign: 'right' }}>
                      <th style={th}>زمان ارسال</th>
                      <th style={th}>فرایند</th>
                      <th style={th}>مرحله</th>
                      <th style={th}>گیرندگان</th>
                      <th style={th}>پیام</th>
                      <th style={th}>وضعیت</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r, i) => (
                      <tr key={`${r.instance_id}-${i}`} style={{ borderBottom: '1px solid #e2e8f0' }}>
                        <td style={td}>{r.fired_at ? formatShamsiTehran(r.fired_at) : '—'}</td>
                        <td style={td}>{PROCESS_LABELS[r.process_code] || r.process_code}</td>
                        <td style={td}>{r.state_code}</td>
                        <td style={td}>
                          {(r.recipients || []).map((rec, j) => (
                            <div key={j} style={{ marginBottom: '0.2rem' }}>
                              <span style={{ fontWeight: 600 }}>{rec.role_fa || labelRoleFa(rec.role)}</span>
                              {rec.delivered ? (
                                <span style={{ color: '#15803d', marginRight: '0.35rem' }}>✓ ارسال شد</span>
                              ) : (
                                <span style={{ color: '#b45309', marginRight: '0.35rem' }}>گیرنده یافت نشد</span>
                              )}
                            </div>
                          ))}
                        </td>
                        <td style={{ ...td, maxWidth: 280 }}>{r.message}</td>
                        <td style={td}>
                          {r.delivered ? (
                            <span style={{ color: '#15803d' }}>ارسال‌شده</span>
                          ) : (
                            <span style={{ color: '#b45309' }}>ثبت‌شده (بدون گیرنده)</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}

    </div>
  )
}

const th = { padding: '0.5rem 0.6rem', fontWeight: 600, color: '#334155', borderBottom: '2px solid #cbd5e1' }
const td = { padding: '0.5rem 0.6rem', verticalAlign: 'top', color: '#334155' }
