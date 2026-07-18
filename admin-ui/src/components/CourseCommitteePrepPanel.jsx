import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { semesterPrepApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { labelState } from '../utils/processDisplay'
import { COMMITTEE_PREP_STATES, pickActiveSemesterPrep } from '../utils/semesterPrepPortalLinks'

const PROCESS_LABELS = {
  fall_semester_preparation: 'آماده‌سازی ترم پاییز',
  winter_semester_preparation: 'آماده‌سازی ترم زمستان',
}

/**
 * کارت آماده‌سازی ترم در پنل کمیته دروس — مسیر مستقیم به workbench.
 */
export default function CourseCommitteePrepPanel({ showToast }) {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await semesterPrepApi.getStatus()
      setStatus(res.data)
    } catch {
      showToast?.('خطا در بارگذاری وضعیت آماده‌سازی ترم', 'error')
      setStatus(null)
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    load()
  }, [load])

  const processes = status?.processes || {}
  const active = pickActiveSemesterPrep(processes)
  const fallDone = Boolean(processes.fall_semester_preparation?.last_completed_at)
  const winterActive = Boolean(processes.winter_semester_preparation?.active)
  const winterDone = Boolean(processes.winter_semester_preparation?.last_completed_at)

  const startPrep = async (processCode) => {
    setBusy(processCode)
    try {
      await semesterPrepApi.start(processCode)
      showToast?.(`${PROCESS_LABELS[processCode] || processCode} شروع شد.`)
      await load()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در شروع فرایند', 'error')
    } finally {
      setBusy(null)
    }
  }

  if (loading) {
    return (
      <div
        className="card"
        style={{ marginBottom: '1.25rem', padding: '1rem' }}
        data-testid="course-committee-prep-panel"
      >
        <p className="muted" style={{ margin: 0 }}>در حال بارگذاری آماده‌سازی ترم…</p>
      </div>
    )
  }

  return (
    <div
      className="card"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.15rem',
        borderRight: '4px solid #2563eb',
        background: 'linear-gradient(180deg, #eff6ff 0%, #fff 100%)',
      }}
      data-testid="course-committee-prep-panel"
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '1rem', flexWrap: 'wrap' }}>
        <div>
          <h3 style={{ margin: '0 0 0.35rem', fontSize: '1rem', color: '#1e40af' }}>
            آماده‌سازی ترم (کمیته دروس)
          </h3>
          <p style={{ margin: 0, fontSize: '0.85rem', color: '#475569', lineHeight: 1.65 }}>
            تقویم آموزشی، لیست دروس و نهایی‌سازی مکان‌ها از اینجا انجام می‌شود.
          </p>
        </div>
        <Link to="/panel/semester-prep" className="btn btn-outline btn-sm" style={{ whiteSpace: 'nowrap' }}>
          همهٔ فرایندها
        </Link>
      </div>

      {active ? (
        <div style={{ marginTop: '0.85rem', padding: '0.75rem', background: '#fff', borderRadius: '8px', border: '1px solid #bfdbfe' }}>
          <p style={{ margin: '0 0 0.35rem', fontWeight: 600, fontSize: '0.9rem' }}>
            {PROCESS_LABELS[active.code]} — {active.entry.state_name_fa || labelState(active.entry.current_state)}
          </p>
          {active.entry.current_state === 'calendar_entry' && active.entry.calendar_sla_deadline_at ? (
            <p style={{ margin: '0 0 0.35rem', fontSize: '0.82rem', color: '#64748b' }}>
              مهلت هدف تقویم: تا {formatShamsiTehran(active.entry.calendar_sla_deadline_at, { dateOnly: true })}
            </p>
          ) : null}
          {active.entry.sla_overdue ? (
            <p style={{ margin: '0 0 0.5rem', fontSize: '0.82rem', color: '#b91c1c' }}>
              مهلت این مرحله گذشته — لطفاً هرچه زودتر تکمیل کنید.
            </p>
          ) : null}
          <Link
            className="btn btn-primary btn-sm"
            to={`/panel/semester-prep/workbench?process_code=${active.code}`}
          >
            {COMMITTEE_PREP_STATES.has(active.entry.current_state) ? 'ادامه کار کمیته' : 'مشاهده workbench'}
          </Link>
        </div>
      ) : (
        <div style={{ marginTop: '0.85rem' }}>
          <p style={{ margin: '0 0 0.65rem', fontSize: '0.85rem', color: '#64748b' }}>
            {!processes.fall_semester_preparation?.active && !fallDone
              ? 'فرایند آماده‌سازی پاییز هنوز شروع نشده است.'
              : fallDone && !winterActive && !winterDone
                ? 'پاییز منتشر شده است؛ آماده‌سازی زمستان هنوز شروع نشده.'
                : 'در حال حاضر مرحله‌ای در اختیار کمیته دروس نیست یا فرایند به پایان رسیده است.'}
          </p>
          {!processes.fall_semester_preparation?.active && !fallDone ? (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={!!busy}
              onClick={() => startPrep('fall_semester_preparation')}
            >
              {busy === 'fall_semester_preparation' ? '…' : 'شروع آماده‌سازی پاییز'}
            </button>
          ) : fallDone && !winterActive && !winterDone ? (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              disabled={!!busy}
              onClick={() => startPrep('winter_semester_preparation')}
            >
              {busy === 'winter_semester_preparation' ? '…' : 'شروع آماده‌سازی زمستان'}
            </button>
          ) : (
            <Link className="btn btn-secondary btn-sm" to="/panel/semester-prep">
              مشاهده وضعیت
            </Link>
          )}
        </div>
      )}
    </div>
  )
}
