import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { semesterPrepApi } from '../services/api'
import PopupToast from '../components/PopupToast'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

const PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی ترم پاییز',
  winter_semester_preparation: 'آماده‌سازی ترم زمستان',
}

export default function SemesterPrepPage() {
  const { user } = useAuth()
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)
  const [toast, setToast] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await semesterPrepApi.getStatus()
      setStatus(res.data)
    } catch (e) {
      setToast({ message: 'خطا در بارگذاری وضعیت آماده‌سازی', type: 'error' })
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const start = async (processCode) => {
    setBusy(processCode)
    try {
      await semesterPrepApi.start(processCode)
      setToast({ message: `${PROCESS_LABELS[processCode] || processCode} شروع شد.`, type: 'success' })
      await load()
    } catch (e) {
      const d = e?.response?.data?.detail
      setToast({ message: typeof d === 'string' ? d : 'خطا در شروع فرایند', type: 'error' })
    } finally {
      setBusy(null)
    }
  }

  const anchorId = status?.anchor_student_id
  const processes = status?.processes || {}

  return (
    <div className="page-container" style={{ maxWidth: 920, margin: '0 auto', padding: '1.25rem' }}>
      <h1 style={{ fontSize: '1.35rem', marginBottom: '0.35rem' }}>آماده‌سازی ترم</h1>
      <p className="muted" style={{ marginBottom: '1.25rem', lineHeight: 1.7 }}>
        شروع و پیگیری فرایندهای آماده‌سازی پاییز و زمستان. شروع خودکار پاییز در ۱۵–۲۰ فروردین و زمستان
        در پنجرهٔ قبل از شروع ترم انجام می‌شود؛ در صورت نیاز می‌توانید دستی هم شروع کنید.
      </p>

      {loading ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {['fall_semester_preparation', 'winter_semester_preparation'].map((code) => {
            const entry = processes[code] || {}
            const active = entry.active
            return (
              <div
                key={code}
                style={{
                  border: '1px solid #e2e8f0',
                  borderRadius: '10px',
                  padding: '1rem 1.15rem',
                  background: active ? '#f0fdf4' : '#fff',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem' }}>
                  <div>
                    <h2 style={{ fontSize: '1.05rem', margin: '0 0 0.35rem' }}>{PROCESS_LABELS[code]}</h2>
                    {active ? (
                      <>
                        <p style={{ margin: '0.25rem 0', fontSize: '0.9rem' }}>
                          مرحله فعلی: <strong>{entry.state_name_fa || entry.current_state}</strong>
                          {entry.sla_overdue ? (
                            <span style={{ color: '#b91c1c', marginRight: '0.5rem' }}> (مهلت گذشته)</span>
                          ) : null}
                        </p>
                        <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b' }}>
                          مسئول: {entry.assigned_role || '—'}
                        </p>
                        {entry.sla_hours ? (
                          <p style={{ margin: '0.35rem 0 0', fontSize: '0.82rem', color: entry.sla_overdue ? '#b91c1c' : '#475569' }}>
                            مهلت مرحله: {entry.sla_hours} ساعت
                            {entry.sla_overdue ? ' — گذشته' : ''}
                          </p>
                        ) : null}
                        {entry.current_state === 'calendar_entry' && entry.calendar_sla_deadline_at ? (
                          <p style={{ margin: '0.25rem 0 0', fontSize: '0.82rem', color: '#475569' }}>
                            مهلت هدف تقویم: تا{' '}
                            {formatShamsiTehran(entry.calendar_sla_deadline_at, { dateOnly: true })}
                          </p>
                        ) : null}
                      </>
                    ) : (
                      <p style={{ margin: 0, fontSize: '0.88rem', color: '#64748b' }}>
                        {code === 'winter_semester_preparation' && !processes.fall_semester_preparation?.last_completed_at
                          ? 'ابتدا آماده‌سازی پاییز باید به «انتشار» برسد.'
                          : 'فرایند فعال نیست.'}
                      </p>
                    )}
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', alignItems: 'flex-end' }}>
                    {!active && (
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={
                          !!busy ||
                          (code === 'winter_semester_preparation' &&
                            !processes.fall_semester_preparation?.last_completed_at)
                        }
                        onClick={() => start(code)}
                      >
                        {busy === code ? '…' : 'شروع فرایند'}
                      </button>
                    )}
                    {active && entry.instance_id && (
                      <>
                        <Link
                          className="btn btn-primary"
                          to={`/panel/semester-prep/workbench?process_code=${code}`}
                        >
                          ادامه مرحله فعلی
                        </Link>
                        <Link
                          className="btn btn-secondary"
                          to={`/panel/students?student_id=${anchorId}&instance_id=${entry.instance_id}`}
                        >
                          باز کردن پرونده
                        </Link>
                      </>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {toast && <PopupToast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  )
}
