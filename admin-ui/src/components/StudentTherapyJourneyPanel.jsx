import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { therapyApi } from '../services/api'
import { canStartProcess } from '../utils/studentProcessAccess'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

const STEPS = [
  {
    id: 'pay',
    title: 'پرداخت جلسات آتی',
    body: 'جلسات تا پایان ترم در تقویم ثبت شده‌اند. هزینهٔ هر جلسه (یا بستهٔ چند جلسه) را از «پرداخت جلسات» تسویه کنید تا لینک و ثبت حضور باز شود.',
  },
  {
    id: 'attend',
    title: 'شرکت در جلسات',
    body: 'از تب «جلسات آنلاین» وارد جلسه شوید. پس از برگزاری، درمانگر حضور/غیاب را ثبت می‌کند و ساعت درمان اضافه می‌شود.',
  },
  {
    id: 'hours',
    title: 'پیگیری ساعات',
    body: 'پیشرفت ساعات درمان را در پروفایل ببینید. تا رسیدن به حدنصاب خاتمه، چرخهٔ پرداخت و حضور ادامه دارد.',
  },
  {
    id: 'complete',
    title: 'خاتمه درمان آموزشی',
    body: 'وقتی ساعات درمان / بالینی / سوپرویژن به حدنصاب رسید، فرایند «خاتمه درمان آموزشی» را شروع کنید.',
  },
]

/**
 * راهنمای مسیر درمان فعال تا خاتمه (therapy_completion) برای داشبورد دانشجو.
 */
export default function StudentTherapyJourneyPanel({
  studentProfile,
  activeProcesses = [],
  completedProcesses = [],
  onStartProcess,
  onOpenSessionPayment,
  onGoToOnlineSessions,
  onOpenTherapyCompletion,
  active = true,
}) {
  const [sessions, setSessions] = useState([])
  const [progress, setProgress] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = useCallback(async () => {
    if (!active || !studentProfile?.therapy_started) return
    setLoading(true)
    try {
      const [sessRes, progRes] = await Promise.all([
        therapyApi.mySessions().catch(() => ({ data: [] })),
        therapyApi.myTherapyProgress().catch(() => ({ data: null })),
      ])
      setSessions(Array.isArray(sessRes.data) ? sessRes.data : [])
      setProgress(progRes?.data || null)
    } catch {
      setSessions([])
      setProgress(null)
    } finally {
      setLoading(false)
    }
  }, [active, studentProfile?.therapy_started])

  useEffect(() => {
    load()
  }, [load])

  const stats = useMemo(() => {
    const scheduled = sessions.filter((s) => s.status === 'scheduled')
    const upcoming = scheduled.filter((s) => {
      const t = Date.parse(s.session_starts_at || s.session_date || '')
      return !Number.isFinite(t) || t >= Date.now() - 86400000
    })
    const unpaidUpcoming = upcoming.filter((s) => s.payment_status === 'pending')
    const paidUpcoming = upcoming.filter(
      (s) => s.payment_status === 'paid' || s.payment_status === 'waived',
    )
    const next = upcoming
      .slice()
      .sort((a, b) => {
        const ta = Date.parse(a.session_starts_at || a.session_date || '') || 0
        const tb = Date.parse(b.session_starts_at || b.session_date || '') || 0
        return ta - tb
      })[0]
    return {
      upcomingCount: upcoming.length,
      unpaidCount: unpaidUpcoming.length,
      paidCount: paidUpcoming.length,
      nextWhen: next
        ? formatShamsiTehran(next.session_starts_at || next.session_date)
        : null,
    }
  }, [sessions])

  const accessCtx = { studentProfile, activeProcesses, completedProcesses }
  const payCheck = canStartProcess('session_payment', accessCtx)
  const completeCheck = canStartProcess('therapy_completion', accessCtx)
  const activePay = (activeProcesses || []).find(
    (p) => p.process_code === 'session_payment' && !p.is_completed && !p.is_cancelled,
  )
  const activeComplete = (activeProcesses || []).find(
    (p) => p.process_code === 'therapy_completion' && !p.is_completed && !p.is_cancelled,
  )
  const therapyDone = (completedProcesses || []).some(
    (p) => p.process_code === 'therapy_completion' && p.current_state === 'therapy_completed',
  )

  if (!studentProfile?.therapy_started || therapyDone) {
    return null
  }

  let activeStep = 'pay'
  if (stats.unpaidCount === 0 && stats.paidCount > 0) activeStep = 'attend'
  const hoursNow = progress?.therapy_hours_2x != null ? Number(progress.therapy_hours_2x) : null
  const hoursGoal = progress?.goal_hours != null ? Number(progress.goal_hours) : 250
  if (hoursNow != null && hoursGoal > 0 && hoursNow >= hoursGoal) {
    activeStep = 'complete'
  } else if (stats.upcomingCount === 0 && stats.unpaidCount === 0) {
    activeStep = 'hours'
  }

  const hoursFa = studentProfile.therapy_hours_progress_fa
    || (hoursNow != null
      ? `${hoursNow.toLocaleString('fa-IR')} / ${hoursGoal.toLocaleString('fa-IR')} ساعت`
      : null)

  return (
    <div
      className="card"
      data-testid="student-therapy-journey-panel"
      style={{ marginBottom: '1rem' }}
    >
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', gap: '0.75rem', flexWrap: 'wrap' }}>
        <h3 className="card-title" style={{ margin: 0 }}>مسیر درمان آموزشی تا خاتمه</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'تازه‌سازی'}
        </button>
      </div>
      <div style={{ padding: '0 1rem 1rem' }}>
        <p style={{ margin: '0 0 0.85rem', fontSize: '0.86rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          جلسات تا پایان ترم در تقویم ثبت می‌شوند؛ پرداخت جلسه‌به‌جلسه (یا بسته‌ای) است.
          {hoursFa ? (
            <>
              {' '}
              پیشرفت فعلی:
              {' '}
              <strong>{hoursFa}</strong>
            </>
          ) : null}
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
            gap: '0.5rem',
            marginBottom: '0.85rem',
          }}
        >
          <div style={{ padding: '0.55rem 0.7rem', borderRadius: 8, background: '#f0fdf4', borderRight: '3px solid #16a34a' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>جلسات پیش‌رو</div>
            <div style={{ fontWeight: 800 }}>{stats.upcomingCount.toLocaleString('fa-IR')}</div>
          </div>
          <div style={{ padding: '0.55rem 0.7rem', borderRadius: 8, background: '#fff7ed', borderRight: '3px solid #ea580c' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>نیاز به پرداخت</div>
            <div style={{ fontWeight: 800 }}>{stats.unpaidCount.toLocaleString('fa-IR')}</div>
          </div>
          <div style={{ padding: '0.55rem 0.7rem', borderRadius: 8, background: '#eff6ff', borderRight: '3px solid #2563eb' }}>
            <div style={{ fontSize: '0.72rem', color: '#64748b' }}>پرداخت‌شدهٔ آماده</div>
            <div style={{ fontWeight: 800 }}>{stats.paidCount.toLocaleString('fa-IR')}</div>
          </div>
        </div>

        {stats.nextWhen && (
          <p style={{ margin: '0 0 0.75rem', fontSize: '0.82rem' }}>
            جلسهٔ بعدی:
            {' '}
            <strong>{stats.nextWhen}</strong>
          </p>
        )}

        <ol style={{ margin: '0 0 1rem', paddingInlineStart: '1.2rem', fontSize: '0.84rem', lineHeight: 1.75 }}>
          {STEPS.map((s) => (
            <li
              key={s.id}
              style={{
                marginBottom: '0.55rem',
                opacity: activeStep === s.id ? 1 : 0.78,
                fontWeight: activeStep === s.id ? 700 : 500,
              }}
            >
              <span>{s.title}</span>
              {activeStep === s.id && (
                <span style={{ marginInlineStart: '0.35rem', color: '#16a34a', fontSize: '0.75rem' }}>
                  (گام فعلی)
                </span>
              )}
              <div style={{ fontWeight: 400, color: '#475569', marginTop: '0.15rem' }}>{s.body}</div>
            </li>
          ))}
        </ol>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
          {(activePay || payCheck.ok) && (
            <button
              type="button"
              className="btn btn-primary btn-sm"
              data-testid="therapy-journey-pay-cta"
              onClick={() => {
                if (activePay && onOpenSessionPayment) onOpenSessionPayment(activePay.instance_id)
                else if (onStartProcess) onStartProcess('session_payment')
              }}
            >
              {activePay ? 'ادامهٔ پرداخت جلسات' : 'شروع پرداخت جلسات'}
            </button>
          )}
          {onGoToOnlineSessions && (
            <button
              type="button"
              className="btn btn-outline btn-sm"
              data-testid="therapy-journey-online-cta"
              onClick={onGoToOnlineSessions}
            >
              جلسات آنلاین
            </button>
          )}
          {(activeComplete || completeCheck.ok) && (
            <button
              type="button"
              className="btn btn-outline btn-sm"
              data-testid="therapy-journey-complete-cta"
              onClick={() => {
                if (activeComplete && onOpenTherapyCompletion) {
                  onOpenTherapyCompletion(activeComplete.instance_id)
                } else if (onStartProcess) {
                  onStartProcess('therapy_completion')
                }
              }}
            >
              {activeComplete ? 'ادامهٔ خاتمه درمان' : 'خاتمه درمان آموزشی'}
            </button>
          )}
        </div>

        {!activePay && !payCheck.ok && payCheck.reasonFa && stats.unpaidCount > 0 && (
          <p style={{ margin: '0.65rem 0 0', fontSize: '0.78rem', color: '#b45309' }}>
            {payCheck.reasonFa}
          </p>
        )}
        {stats.upcomingCount === 0 && !loading && (
          <p style={{ margin: '0.65rem 0 0', fontSize: '0.82rem', color: '#64748b' }} data-testid="therapy-journey-empty-hint">
            اگر جلسهٔ پیش‌رویی نمی‌بینید، صفحه را تازه کنید تا سامانه تقویم تا پایان ترم را تکمیل کند؛
            سپس «پرداخت جلسات» فعال می‌شود.
          </p>
        )}
      </div>
    </div>
  )
}
