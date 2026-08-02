import React, { useCallback, useEffect, useMemo, useState } from 'react'
import { semesterPrepApi } from '../services/api'
import ShamsiDatePicker from './ShamsiDatePicker'
import {
  INTERVIEW_COURSE_TYPES,
  INTERVIEW_COURSE_LABELS_FA,
  SESSION_MINUTE_OPTIONS,
  buildInterviewSetupBody,
  countGroupSessions,
  countSetupSessions,
  describeGroupPlan,
  emptyInterviewSetup,
  interviewSetupErrors,
  interviewSetupFromContext,
} from '../utils/semesterPrepInterviewPlan'
import {
  defaultShamsiDate,
  shamsiDateToIsoDate,
  formatShamsiTehran,
} from '../utils/shamsiDateTime'

/** نقش‌هایی که می‌توانند مرحلهٔ مصاحبه‌ها را ثبت کنند */
const EDITOR_ROLES = new Set(['admin', 'deputy_education', 'staff', 'site_manager'])

export function canEditInterviewSetup(role) {
  return EDITOR_ROLES.has(String(role || '').trim())
}

function shamsiLabel(isoDate) {
  return formatShamsiTehran(isoDate, { dateOnly: true })
}

function CourseTypeCard({ courseType, group, candidates, disabled, onChange, onCopyFrom }) {
  const labelFa = INTERVIEW_COURSE_LABELS_FA[courseType]
  const [pickerDate, setPickerDate] = useState(defaultShamsiDate)

  const patch = (next) => onChange({ ...group, ...next })

  const toggleInterviewer = (id) => {
    const has = group.interviewerIds.includes(id)
    patch({
      interviewerIds: has
        ? group.interviewerIds.filter((x) => x !== id)
        : [...group.interviewerIds, id],
    })
  }

  const addDate = () => {
    const iso = shamsiDateToIsoDate(pickerDate.jy, pickerDate.jm, pickerDate.jd)
    if (group.dates.includes(iso)) return
    patch({ dates: [...group.dates, iso].sort() })
  }

  const removeDate = (iso) => patch({ dates: group.dates.filter((d) => d !== iso) })

  const summary = describeGroupPlan(group)

  return (
    <section
      data-testid={`interview-setup-card-${courseType}`}
      style={{
        background: '#fff',
        border: '1px solid #dbeafe',
        borderRadius: '10px',
        padding: '0.9rem 1rem',
        marginBottom: '0.9rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.7rem' }}>
        <h5 style={{ margin: 0, fontSize: '0.9rem', fontWeight: 700, color: '#1e40af' }}>
          مصاحبه {labelFa}
        </h5>
        {onCopyFrom && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            disabled={disabled}
            onClick={onCopyFrom}
            data-testid={`interview-setup-copy-${courseType}`}
          >
            مثل دوره جامع
          </button>
        )}
      </div>

      <div style={{ marginBottom: '0.8rem' }}>
        <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.35rem' }}>
          مصاحبه‌گرها (از کارمندان اتوماسیون)
        </div>
        {candidates.length === 0 ? (
          <p className="muted" style={{ fontSize: '0.8rem', margin: 0 }}>
            کارمند فعالی برای انتخاب یافت نشد.
          </p>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {candidates.map((c) => {
              const active = group.interviewerIds.includes(c.id)
              return (
                <button
                  key={c.id}
                  type="button"
                  disabled={disabled}
                  onClick={() => toggleInterviewer(c.id)}
                  data-testid={`interview-setup-${courseType}-user-${c.id}`}
                  style={{
                    border: active ? '1px solid #2563eb' : '1px solid #cbd5e1',
                    background: active ? '#dbeafe' : '#f8fafc',
                    color: active ? '#1e3a8a' : '#334155',
                    fontWeight: active ? 700 : 500,
                    borderRadius: '999px',
                    padding: '0.3rem 0.7rem',
                    fontSize: '0.8rem',
                    cursor: disabled ? 'default' : 'pointer',
                  }}
                >
                  {active ? '✓ ' : ''}
                  {c.full_name_fa}
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div style={{ marginBottom: '0.8rem' }}>
        <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.35rem' }}>
          روزهای مصاحبه
        </div>
        <div className="interview-setup-date-row">
          <ShamsiDatePicker
            value={pickerDate}
            onChange={setPickerDate}
            idPrefix={`interview-setup-${courseType}-date`}
            compact
            disabled={disabled}
          />
          <button
            type="button"
            className="btn btn-secondary btn-sm interview-setup-date-row__add"
            disabled={disabled}
            onClick={addDate}
            data-testid={`interview-setup-${courseType}-add-date`}
          >
            افزودن روز
          </button>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', marginTop: '0.5rem' }}>
          {group.dates.map((iso) => (
            <span
              key={iso}
              style={{
                background: '#eff6ff',
                border: '1px solid #bfdbfe',
                borderRadius: '999px',
                padding: '0.25rem 0.6rem',
                fontSize: '0.78rem',
                display: 'inline-flex',
                gap: '0.35rem',
                alignItems: 'center',
              }}
            >
              {shamsiLabel(iso)}
              {!disabled && (
                <button
                  type="button"
                  onClick={() => removeDate(iso)}
                  aria-label={`حذف ${iso}`}
                  style={{ border: 'none', background: 'none', color: '#b91c1c', cursor: 'pointer' }}
                >
                  ×
                </button>
              )}
            </span>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem' }}>
        <label style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          ساعت شروع
          <input
            type="time"
            className="form-input psf-input"
            value={group.startTime}
            disabled={disabled}
            data-testid={`interview-setup-${courseType}-start`}
            onChange={(e) => patch({ startTime: e.target.value })}
          />
        </label>
        <label style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          ساعت پایان
          <input
            type="time"
            className="form-input psf-input"
            value={group.endTime}
            disabled={disabled}
            data-testid={`interview-setup-${courseType}-end`}
            onChange={(e) => patch({ endTime: e.target.value })}
          />
        </label>
        <label style={{ fontSize: '0.8rem', display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
          مدت هر نوبت
          <select
            className="form-input psf-input"
            value={group.sessionMinutes}
            disabled={disabled}
            data-testid={`interview-setup-${courseType}-minutes`}
            onChange={(e) => patch({ sessionMinutes: Number(e.target.value) })}
          >
            {SESSION_MINUTE_OPTIONS.map((m) => (
              <option key={m} value={m}>{`${m} دقیقه`}</option>
            ))}
          </select>
        </label>
      </div>

      <p
        data-testid={`interview-setup-${courseType}-summary`}
        style={{ fontSize: '0.8rem', color: countGroupSessions(group) ? '#166534' : '#b45309', margin: '0.6rem 0 0' }}
      >
        {summary || 'هنوز نوبتی ساخته نمی‌شود — مصاحبه‌گر، روز و ساعت را کامل کنید.'}
      </p>
    </section>
  )
}

/**
 * مرحلهٔ یکپارچهٔ «مصاحبه‌ها» — جایگزین گام‌های ۷ و ۸ آماده‌سازی ترم.
 */
export default function SemesterPrepInterviewSetupPanel({
  instanceId,
  contextData,
  role,
  showToast,
  onUpdated,
  onPublished = null,
}) {
  const [setup, setSetup] = useState(emptyInterviewSetup)
  const [candidates, setCandidates] = useState([])
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState([])

  const disabled = !canEditInterviewSetup(role) || busy

  useEffect(() => {
    let cancelled = false
    semesterPrepApi
      .getInterviewCandidates()
      .then((res) => {
        if (cancelled) return
        const list = Array.isArray(res.data?.candidates) ? res.data.candidates : []
        setCandidates(list)
      })
      .catch(() => {
        if (!cancelled) setCandidates([])
      })
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    setSetup(interviewSetupFromContext(contextData))
  }, [contextData])

  const patchGroup = useCallback(
    (courseType, next) => setSetup((prev) => ({ ...prev, [courseType]: next })),
    [],
  )

  const totalSessions = useMemo(() => countSetupSessions(setup), [setup])

  const submit = async () => {
    const found = interviewSetupErrors(setup)
    if (found.length) {
      setErrors(found)
      showToast?.(`${found.length} مورد باید اصلاح شود`, 'error')
      return
    }
    setErrors([])
    setBusy(true)
    try {
      const res = await semesterPrepApi.saveInterviewSetup(
        buildInterviewSetupBody(setup, instanceId),
      )
      const created = res.data?.created_slots?.total ?? 0
      showToast?.(`مرحلهٔ مصاحبه‌ها ثبت شد — ${created} نوبت قابل رزرو ساخته شد.`)
      onUpdated?.(res.data?.context_data)
      if (res.data?.current_state === 'published') onPublished?.()
    } catch (e) {
      const detail = e?.response?.data?.detail
      if (detail && typeof detail === 'object' && Array.isArray(detail.missing)) {
        setErrors(detail.missing)
        showToast?.('ثبت انجام نشد؛ موارد مشخص‌شده را اصلاح کنید.', 'error')
      } else {
        showToast?.(typeof detail === 'string' ? detail : 'خطا در ثبت مرحلهٔ مصاحبه‌ها', 'error')
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <div data-testid="semester-prep-interview-setup">
      <p style={{ fontSize: '0.82rem', color: '#334155', margin: '0 0 0.85rem', lineHeight: 1.7 }}>
        مصاحبه‌گرها را از میان کارمندان اتوماسیون انتخاب کنید و روز و ساعت مصاحبه‌ها را مشخص
        کنید. نوبت‌های قابل رزرو خودکار ساخته می‌شوند و با ثبت همین فرم، تقویم منتشر می‌شود.
      </p>

      <section
        style={{
          background: '#fff',
          border: '1px solid #dbeafe',
          borderRadius: '10px',
          padding: '0.9rem 1rem',
          marginBottom: '0.9rem',
        }}
      >
        <div style={{ fontSize: '0.82rem', fontWeight: 600, marginBottom: '0.4rem' }}>
          نوع برگزاری
        </div>
        <div style={{ display: 'flex', gap: '1.2rem', flexWrap: 'wrap' }}>
          {['آنلاین', 'حضوری'].map((mode) => (
            <label key={mode} style={{ fontSize: '0.85rem', display: 'flex', gap: '0.35rem', alignItems: 'center' }}>
              <input
                type="radio"
                name="interview-setup-mode"
                value={mode}
                disabled={disabled}
                checked={setup.interviewMode === mode}
                data-testid={`interview-setup-mode-${mode === 'آنلاین' ? 'online' : 'in-person'}`}
                onChange={() => setSetup((prev) => ({ ...prev, interviewMode: mode }))}
              />
              {mode}
            </label>
          ))}
        </div>
        {setup.interviewMode === 'حضوری' && (
          <label style={{ display: 'block', marginTop: '0.7rem', fontSize: '0.8rem' }}>
            آدرس یا محل برگزاری
            <textarea
              className="form-input psf-input"
              rows={2}
              value={setup.interviewLocationFa}
              disabled={disabled}
              data-testid="interview-setup-location"
              onChange={(e) => setSetup((prev) => ({ ...prev, interviewLocationFa: e.target.value }))}
            />
          </label>
        )}
        {setup.interviewMode === 'آنلاین' && (
          <p className="muted" style={{ fontSize: '0.78rem', margin: '0.5rem 0 0', lineHeight: 1.6 }}>
            لینک جلسه پس از پرداخت هزینهٔ مصاحبه به‌صورت خودکار در الوکام ساخته می‌شود.
          </p>
        )}
      </section>

      {INTERVIEW_COURSE_TYPES.map((courseType) => (
        <CourseTypeCard
          key={courseType}
          courseType={courseType}
          group={setup[courseType]}
          candidates={candidates}
          disabled={disabled}
          onChange={(next) => patchGroup(courseType, next)}
          onCopyFrom={
            courseType === 'introductory'
              ? () => patchGroup('introductory', { ...setup.comprehensive })
              : null
          }
        />
      ))}

      {errors.length > 0 && (
        <ul
          data-testid="interview-setup-errors"
          style={{
            background: '#fef2f2',
            border: '1px solid #fecaca',
            borderRadius: '8px',
            padding: '0.6rem 1.4rem',
            margin: '0 0 0.85rem',
            fontSize: '0.8rem',
            color: '#991b1b',
            lineHeight: 1.8,
          }}
        >
          {errors.map((msg) => (
            <li key={msg}>{msg}</li>
          ))}
        </ul>
      )}

      <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          disabled={disabled}
          onClick={submit}
          data-testid="interview-setup-submit"
        >
          {busy ? 'در حال ثبت…' : 'ثبت مصاحبه‌ها و انتشار تقویم'}
        </button>
        <span style={{ fontSize: '0.8rem', color: '#475569' }}>
          {`مجموع نوبت‌های ساخته‌شده: ${totalSessions}`}
        </span>
      </div>

      {!canEditInterviewSetup(role) && (
        <p style={{ fontSize: '0.8rem', color: '#b45309', marginTop: '0.6rem' }}>
          ثبت این مرحله فقط برای معاون آموزش، مدیر داخلی و مدیر سیستم مجاز است.
        </p>
      )}
    </div>
  )
}
