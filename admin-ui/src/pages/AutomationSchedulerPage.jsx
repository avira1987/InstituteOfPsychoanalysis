import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { useAuth } from '../contexts/AuthContext'
import { schedulerApi } from '../services/api'
import { useToast } from '../contexts/ToastContext'
import ShamsiDatePicker from '../components/ShamsiDatePicker'
import ShamsiDateTimePicker from '../components/ShamsiDateTimePicker'
import {
  defaultShamsiDate,
  defaultShamsiTehranNow,
  formatShamsiTehran,
  isoDateToShamsiParts,
  shamsiDateTimeToUtcIso,
  shamsiDateToIsoDate,
  utcIsoToShamsiTehran,
} from '../utils/shamsiDateTime'

const MODE_LABELS = {
  reminder_queue: 'یادآوری صف‌دار',
  instance_sla: 'مهلت SLA',
  calendar_date: 'تاریخ تقویم',
  milestone: 'نقطه عطف',
  batch_start: 'شروع دسته‌ای',
  daily_overdue_digest: 'چک روزانه عقب‌افتاده',
}

function emptyForm() {
  return {
    term_code: '',
    term_start_date: defaultShamsiDate(),
    term_end_date: defaultShamsiDate(),
    registration_open_at: defaultShamsiTehranNow(),
    registration_deadline_at: defaultShamsiTehranNow(),
    evaluation_open_at: defaultShamsiTehranNow(),
    evaluation_close_at: defaultShamsiTehranNow(),
  }
}

function partsToIsoDate(parts) {
  if (!parts?.jy) return null
  try {
    return shamsiDateToIsoDate(parts.jy, parts.jm, parts.jd)
  } catch {
    return null
  }
}

function partsToIsoDateTime(parts) {
  if (!parts?.jy) return null
  try {
    return shamsiDateTimeToUtcIso(parts.jy, parts.jm, parts.jd, parts.hour ?? 0, parts.minute ?? 0)
  } catch {
    return null
  }
}

function formatDateParts(parts) {
  const iso = partsToIsoDate(parts)
  return iso ? formatShamsiTehran(iso, { dateOnly: true }) : '—'
}

function formatDateTimeParts(parts) {
  const iso = partsToIsoDateTime(parts)
  return iso ? formatShamsiTehran(iso) : '—'
}

function TimelineItem({ label, value, highlight }) {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        gap: '1rem',
        padding: '0.55rem 0',
        borderBottom: '1px solid var(--border)',
        fontSize: '0.9rem',
      }}
    >
      <span style={{ color: 'var(--text-secondary)' }}>{label}</span>
      <strong style={{ color: highlight ? 'var(--primary)' : 'inherit' }}>{value}</strong>
    </div>
  )
}

export default function AutomationSchedulerPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [tab, setTab] = useState('calendar')
  const [form, setForm] = useState(emptyForm)
  const [publishedAt, setPublishedAt] = useState(null)
  const [indexData, setIndexData] = useState(null)
  const [runSummary, setRunSummary] = useState(null)
  const [dailyRuns, setDailyRuns] = useState([])
  const [dailyRunning, setDailyRunning] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [filter, setFilter] = useState('')
  const { showToast } = useToast()

  const loadAll = useCallback(async () => {
    setLoading(true)
    try {
      const [calRes, idxRes, dailyRes] = await Promise.all([
        schedulerApi.getActiveCalendar(),
        schedulerApi.getAutomationIndex(),
        schedulerApi.getDailyOverdueRuns(30).catch(() => ({ data: { runs: [] } })),
      ])
      const cal = calRes.data
      if (cal) {
        setForm({
          term_code: cal.term_code || '',
          term_start_date: isoDateToShamsiParts(cal.term_start_date) || defaultShamsiDate(),
          term_end_date: isoDateToShamsiParts(cal.term_end_date) || defaultShamsiDate(),
          registration_open_at: utcIsoToShamsiTehran(cal.registration_open_at) || defaultShamsiTehranNow(),
          registration_deadline_at: utcIsoToShamsiTehran(cal.registration_deadline_at) || defaultShamsiTehranNow(),
          evaluation_open_at: utcIsoToShamsiTehran(cal.evaluation_open_at) || defaultShamsiTehranNow(),
          evaluation_close_at: utcIsoToShamsiTehran(cal.evaluation_close_at) || defaultShamsiTehranNow(),
        })
        setPublishedAt(cal.published_at)
      } else {
        setForm(emptyForm())
        setPublishedAt(null)
      }
      setIndexData(idxRes.data)
      setDailyRuns(dailyRes.data?.runs || [])
    } catch (err) {
      showToast(err?.response?.data?.detail || 'بارگذاری ناموفق بود', 'error')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadAll()
  }, [loadAll])

  const processRows = useMemo(() => {
    const procs = indexData?.processes || {}
    const q = filter.trim().toLowerCase()
    return Object.entries(procs)
      .filter(([code, meta]) => {
        if (!q) return true
        const name = meta?.completion_role || ''
        return code.includes(q) || name.includes(q) || (meta?.mode || '').includes(q)
      })
      .sort(([a], [b]) => a.localeCompare(b))
  }, [indexData, filter])

  const handleSave = async (e) => {
    e.preventDefault()
    if (!isAdmin) return
    if (!form.term_code.trim()) {
      showToast('کد ترم الزامی است', 'error')
      return
    }
    setSaving(true)
    try {
      const body = {
        term_code: form.term_code.trim(),
        term_start_date: partsToIsoDate(form.term_start_date),
        term_end_date: partsToIsoDate(form.term_end_date),
        registration_open_at: partsToIsoDateTime(form.registration_open_at),
        registration_deadline_at: partsToIsoDateTime(form.registration_deadline_at),
        evaluation_open_at: partsToIsoDateTime(form.evaluation_open_at),
        evaluation_close_at: partsToIsoDateTime(form.evaluation_close_at),
      }
      const res = await schedulerApi.saveActiveCalendar(body)
      setPublishedAt(res.data.published_at)
      showToast('تقویم آموزشی ذخیره و روی دانشجویان فعال sync شد')
    } catch (err) {
      showToast(err?.response?.data?.detail || 'ذخیره ناموفق بود', 'error')
    } finally {
      setSaving(false)
    }
  }

  const handleRunDailyOverdue = async () => {
    if (!isAdmin) return
    setDailyRunning(true)
    try {
      const res = await schedulerApi.runDailyOverdue()
      showToast(
        `چک روزانه: ${res.data.tasks_found ?? 0} کار، ${res.data.sms_sent ?? 0} SMS، ${res.data.notifications_created ?? 0} اعلان`
      )
      const dailyRes = await schedulerApi.getDailyOverdueRuns(30)
      setDailyRuns(dailyRes.data?.runs || [])
      setTab('daily')
    } catch (err) {
      showToast(err?.response?.data?.detail || 'اجرای چک روزانه ناموفق بود', 'error')
    } finally {
      setDailyRunning(false)
    }
  }

  const handleRunPass = async () => {
    if (!isAdmin) return
    setRunning(true)
    setRunSummary(null)
    try {
      const res = await schedulerApi.runPass()
      setRunSummary(res.data)
      showToast('یک دور اتوماسیون با موفقیت اجرا شد')
      setTab('run')
    } catch (err) {
      showToast(err?.response?.data?.detail || 'اجرای دستی ناموفق بود', 'error')
    } finally {
      setRunning(false)
    }
  }

  const summaryCounts = runSummary
    ? [
        ['scheduled_reminders', 'یادآورهای صف'],
        ['installment_overdue', 'سررسید اقساط'],
        ['generic_sla_triggers', 'SLA عمومی'],
        ['academic_term_batch', 'رویدادهای ترم'],
        ['student_milestones', 'Milestone انترن/TA'],
        ['start_therapy_week9', 'هفته ۹ درمان'],
        ['lms_session_hooks', 'جلسات LMS'],
        ['payment_timeout', 'مهلت پرداخت'],
        ['send_return_reminder', 'یادآور بازگشت مرخصی'],
      ].map(([key, label]) => ({
        key,
        label,
        count: Array.isArray(runSummary[key]) ? runSummary[key].length : 0,
      }))
    : []

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">اتوماسیون زمان‌محور</h1>
          <p className="page-subtitle">
            تقویم آموزشی فعال، فرایندهای زمان‌دار، و اجرای دستی scheduler
            {publishedAt ? ` — آخرین انتشار: ${formatShamsiTehran(publishedAt)}` : ''}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          <button type="button" className="btn btn-outline" onClick={loadAll} disabled={loading}>
            {loading ? '…' : 'بازخوانی'}
          </button>
          {isAdmin ? (
            <button type="button" className="btn btn-outline" onClick={handleRunDailyOverdue} disabled={dailyRunning}>
              {dailyRunning ? 'چک روزانه…' : 'اجرای چک روزانه'}
            </button>
          ) : null}
          {isAdmin ? (
            <button type="button" className="btn btn-primary" onClick={handleRunPass} disabled={running}>
              {running ? 'در حال اجرا…' : 'اجرای دستی یک دور'}
            </button>
          ) : null}
        </div>
      </div>

      <div className="card" style={{ padding: '0.35rem 0.75rem', marginBottom: '1rem', display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
        {[
          ['calendar', 'تقویم ترم'],
          ['processes', 'فرایندهای زمان‌دار'],
          ['daily', 'چک روزانه'],
          ['run', 'نتیجهٔ اجرا'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`btn ${tab === id ? 'btn-primary' : 'btn-outline'}`}
            style={{ fontSize: '0.88rem' }}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="card" style={{ padding: '1.25rem' }}>
          <p className="muted" style={{ margin: 0 }}>در حال بارگذاری…</p>
        </div>
      ) : null}

      {!loading && tab === 'calendar' ? (
        <div style={{ display: 'grid', gap: '1rem', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
          <form className="card" style={{ padding: '1.25rem' }} onSubmit={handleSave}>
            <h3 className="card-title" style={{ marginTop: 0 }}>تقویم آموزشی فعال</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 0 }}>
              پس از ذخیره، `term_start_date` روی پروندهٔ دانشجویان فعال sync می‌شود و scheduler از این تاریخ‌ها استفاده می‌کند.
            </p>
            {!isAdmin ? (
              <p style={{ color: 'var(--warning)', fontSize: '0.85rem' }}>فقط ادمین می‌تواند تقویم را ویرایش کند.</p>
            ) : null}

            <label className="form-label">کد ترم *</label>
            <input
              className="form-input"
              value={form.term_code}
              onChange={(e) => setForm((f) => ({ ...f, term_code: e.target.value }))}
              placeholder="مثلاً fall-1405"
              disabled={!isAdmin}
              required
            />

            <ShamsiDatePicker
              label="شروع ترم"
              idPrefix="term-start"
              value={form.term_start_date}
              onChange={(v) => setForm((f) => ({ ...f, term_start_date: v }))}
              disabled={!isAdmin}
            />

            <ShamsiDatePicker
              label="پایان ترم"
              idPrefix="term-end"
              value={form.term_end_date}
              onChange={(v) => setForm((f) => ({ ...f, term_end_date: v }))}
              disabled={!isAdmin}
            />

            <ShamsiDateTimePicker
              label="شروع ثبت‌نام"
              idPrefix="reg-open"
              value={form.registration_open_at}
              onChange={(v) => setForm((f) => ({ ...f, registration_open_at: v }))}
              compact
              disabled={!isAdmin}
            />

            <ShamsiDateTimePicker
              label="مهلت ثبت‌نام"
              idPrefix="reg-deadline"
              value={form.registration_deadline_at}
              onChange={(v) => setForm((f) => ({ ...f, registration_deadline_at: v }))}
              compact
              disabled={!isAdmin}
            />

            <ShamsiDateTimePicker
              label="شروع ارزیابی اساتید"
              idPrefix="eval-open"
              value={form.evaluation_open_at}
              onChange={(v) => setForm((f) => ({ ...f, evaluation_open_at: v }))}
              compact
              disabled={!isAdmin}
            />

            <ShamsiDateTimePicker
              label="پایان ارزیابی اساتید"
              idPrefix="eval-close"
              value={form.evaluation_close_at}
              onChange={(v) => setForm((f) => ({ ...f, evaluation_close_at: v }))}
              compact
              disabled={!isAdmin}
            />

            {isAdmin ? (
              <button type="submit" className="btn btn-primary" style={{ marginTop: '1rem' }} disabled={saving}>
                {saving ? 'در حال ذخیره…' : 'ذخیره و sync دانشجویان'}
              </button>
            ) : null}
          </form>

          <div className="card" style={{ padding: '1.25rem' }}>
            <h3 className="card-title" style={{ marginTop: 0 }}>خط زمان ترم</h3>
            <TimelineItem label="شروع ترم" value={formatDateParts(form.term_start_date)} highlight />
            <TimelineItem label="باز شدن ثبت‌نام" value={formatDateTimeParts(form.registration_open_at)} />
            <TimelineItem label="مهلت ثبت‌نام" value={formatDateTimeParts(form.registration_deadline_at)} highlight />
            <TimelineItem label="شروع ارزیابی" value={formatDateTimeParts(form.evaluation_open_at)} />
            <TimelineItem label="پایان ارزیابی" value={formatDateTimeParts(form.evaluation_close_at)} />
            <TimelineItem label="پایان ترم" value={formatDateParts(form.term_end_date)} highlight />
            <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '1rem', marginBottom: 0 }}>
              انتشار از فرایند «آماده‌سازی ترم» نیز با اکشن `publish_academic_calendar_to_profiles` همین رکورد را به‌روز می‌کند.
            </p>
          </div>
        </div>
      ) : null}

      {!loading && tab === 'processes' ? (
        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>
              فرایندهای زمان‌دار ({processRows.length})
            </h3>
            <input
              className="form-input"
              style={{ maxWidth: 280 }}
              placeholder="جستجو کد فرایند…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          </div>
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
              <thead>
                <tr>
                  <th>کد فرایند</th>
                  <th>نوع</th>
                  <th>نقش تکمیل</th>
                  <th>تریگرها</th>
                </tr>
              </thead>
              <tbody>
                {processRows.map(([code, meta]) => (
                  <tr key={code}>
                    <td>
                      <code style={{ fontSize: '0.82rem' }}>{code}</code>
                    </td>
                    <td>{MODE_LABELS[meta.mode] || meta.mode || '—'}</td>
                    <td>{meta.completion_role || '—'}</td>
                    <td>
                      {(meta.triggers || [])
                        .map((t) => t.event)
                        .filter(Boolean)
                        .join('، ') || '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)', marginTop: '1rem', marginBottom: 0 }}>
            منبع: `metadata/scheduled_automation_index.json` — اجرا هر ~۵ دقیقه در پس‌زمینه (`CALENDAR_TRIGGER_INTERVAL_SECONDS`).
          </p>
        </div>
      ) : null}

      {!loading && tab === 'daily' ? (
        <div className="card" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <h3 className="card-title" style={{ margin: 0 }}>
              چک روزانه کارهای عقب‌افتاده (ساعت ۸ تهران)
            </h3>
            {isAdmin ? (
              <button type="button" className="btn btn-primary" onClick={handleRunDailyOverdue} disabled={dailyRunning}>
                {dailyRunning ? 'در حال اجرا…' : 'اجرای دستی چک روزانه'}
              </button>
            ) : null}
          </div>
          <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: 0 }}>
            هر روز پس از ساعت ۸ صبح (Asia/Tehran)، کارهای عقب‌افتاده شناسایی می‌شوند؛ SMS هشدار و اعلان پنل با لینک مستقیم ثبت می‌شود.
          </p>
          {!dailyRuns.length ? (
            <p className="muted" style={{ margin: 0 }}>هنوز اجرایی ثبت نشده است.</p>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
                <thead>
                  <tr>
                    <th>تاریخ (تهران)</th>
                    <th>شروع</th>
                    <th>کارها</th>
                    <th>SMS</th>
                    <th>اعلان</th>
                    <th>dedup</th>
                    <th>منبع</th>
                    <th>جزئیات</th>
                  </tr>
                </thead>
                <tbody>
                  {dailyRuns.map((run) => (
                    <tr key={run.id}>
                      <td>{run.run_date_tehran || '—'}</td>
                      <td>{run.started_at ? formatShamsiTehran(run.started_at) : '—'}</td>
                      <td>{run.tasks_found ?? 0}</td>
                      <td>{run.sms_sent ?? 0}</td>
                      <td>{run.notifications_created ?? 0}</td>
                      <td>{run.skipped_dedup ?? 0}</td>
                      <td>{run.triggered_by === 'manual' ? 'دستی' : 'زمان‌بند'}</td>
                      <td>
                        <details>
                          <summary style={{ cursor: 'pointer' }}>{(run.details || []).length} مورد</summary>
                          <pre style={{ fontSize: '0.72rem', maxWidth: 420, overflow: 'auto' }}>
                            {JSON.stringify(run.details || [], null, 2)}
                          </pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : null}

      {!loading && tab === 'run' ? (
        <div className="card" style={{ padding: '1.25rem' }}>
          <h3 className="card-title" style={{ marginTop: 0 }}>نتیجهٔ آخرین اجرای دستی</h3>
          {!runSummary ? (
            <p className="muted" style={{ margin: 0 }}>
              هنوز اجرایی انجام نشده. دکمه «اجرای دستی یک دور» را بزنید (فقط ادمین).
            </p>
          ) : (
            <>
              <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)' }}>
                زمان: {formatShamsiTehran(runSummary.at)} — رویدادهای ثبت‌شده: {runSummary.fired_total ?? runSummary.scheduler_fired_total ?? 0}
              </p>
              <div
                style={{
                  display: 'grid',
                  gap: '0.75rem',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))',
                  marginBottom: '1rem',
                }}
              >
                {summaryCounts.map(({ key, label, count }) => (
                  <div key={key} className="card" style={{ padding: '0.75rem 1rem', background: 'var(--bg-secondary)' }}>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>{label}</div>
                    <div style={{ fontSize: '1.35rem', fontWeight: 700, color: count > 0 ? 'var(--primary)' : 'inherit' }}>{count}</div>
                  </div>
                ))}
              </div>
              <details>
                <summary style={{ cursor: 'pointer', marginBottom: '0.5rem' }}>JSON کامل پاسخ</summary>
                <pre
                  style={{
                    maxHeight: 360,
                    overflow: 'auto',
                    fontSize: '0.75rem',
                    background: 'var(--bg-secondary)',
                    padding: '0.75rem',
                    borderRadius: 8,
                  }}
                >
                  {JSON.stringify(runSummary, null, 2)}
                </pre>
              </details>
            </>
          )}
        </div>
      ) : null}
    </div>
  )
}
