import React from 'react'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { fmtRialDisplay } from '../utils/marketingHandoffDisplay'
import {
  CALENDAR_FIELD_ROWS,
  INTERVIEW_FIELD_ROWS,
  LICENSE_FIELD_ROWS,
  MARKETING_FIELD_ROWS,
  TUITION_FIELD_ROWS,
  hasRecordedPrepData,
  interviewPlanGroups,
  recordedValuePresent,
  shouldShowPrepRecordedSummary,
  visibleCourseTables,
} from '../utils/semesterPrepRecordedSummary'

const RIAL_KEYS = new Set([
  'per_unit_cost_introductory',
  'per_unit_cost_comprehensive',
  'interview_fee_introductory',
  'interview_fee_comprehensive',
  'registration_interview_fee_rial',
  'start_therapy_first_session_fee_rial',
  'extra_session_fee_rial',
])

function formatDate(value) {
  if (!value) return null
  return formatShamsiTehran(value, { dateOnly: true })
}

function formatBreakPeriods(periods) {
  if (!Array.isArray(periods) || !periods.length) return null
  const parts = periods
    .filter((item) => item && (item.start || item.end))
    .map((item) => {
      const start = formatDate(item.start) || '—'
      const end = formatDate(item.end) || '—'
      return `${start} تا ${end}`
    })
  return parts.length ? parts.join('؛ ') : null
}

function formatBool(value) {
  if (value === true) return 'بله'
  if (value === false) return 'خیر'
  return null
}

function formatScalar(key, value) {
  if (value == null || value === '') return null
  if (typeof value === 'boolean') return formatBool(value)
  if (RIAL_KEYS.has(key)) return fmtRialDisplay(value)
  if (key === 'default_therapy_session_fee_toman') {
    const n = Number(value)
    if (Number.isFinite(n)) return `${n.toLocaleString('fa-IR')} تومان`
  }
  if (key === 'slot_duration_minutes') {
    const n = Number(value)
    if (Number.isFinite(n)) return `${n.toLocaleString('fa-IR')} دقیقه`
  }
  if (Array.isArray(value)) {
    const labels = value.map((item) => (item == null ? '' : String(item).trim())).filter(Boolean)
    return labels.length ? labels.join('، ') : null
  }
  if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)) {
    return formatDate(value) || value
  }
  return String(value)
}

function Row({ label, value }) {
  if (value == null || value === '') return null
  return (
    <div className="semester-prep-recorded-summary__row">
      <span className="semester-prep-recorded-summary__label">{label}</span>
      <span className="semester-prep-recorded-summary__value">{value}</span>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <section className="semester-prep-recorded-summary__section">
      <h4 className="semester-prep-recorded-summary__section-title">{title}</h4>
      {children}
    </section>
  )
}

function FieldRows({ rows, data, skipKeys }) {
  const skip = skipKeys || new Set()
  const source = data && typeof data === 'object' ? data : {}
  return rows.map(([key, label]) => {
    if (skip.has(key)) return null
    return <Row key={key} label={label} value={formatScalar(key, source[key])} />
  })
}

function CourseTable({ def, rows }) {
  const usedCols = def.columns.filter((col) =>
    rows.some((row) => row && recordedValuePresent(row[col[0]])),
  )
  const columns = usedCols.length ? usedCols : def.columns.slice(0, 4)
  return (
    <div className="semester-prep-recorded-summary__table-wrap">
      <div className="semester-prep-recorded-summary__table-caption">{def.label}</div>
      <table>
        <thead>
          <tr>
            {columns.map(([key, label]) => (
              <th key={key}>{label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              {columns.map(([key]) => (
                <td key={key}>{formatScalar(key, row?.[key]) || '—'}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function InterviewPlan({ plan }) {
  const groups = interviewPlanGroups(plan)
  if (!groups.length) return null
  return (
    <div>
      {groups.map(({ key, label, group }) => {
        const schedules = Array.isArray(group?.interviewers) ? group.interviewers : []
        return (
          <div key={key} className="semester-prep-recorded-summary__plan">
            <div className="semester-prep-recorded-summary__plan-title">{label}</div>
            <Row
              label="مصاحبه‌گرها"
              value={formatScalar('comprehensive_interviewers', group.interviewer_ids)}
            />
            <Row
              label="مدت هر نوبت"
              value={formatScalar('slot_duration_minutes', group.session_minutes)}
            />
            {schedules.map((schedule, idx) => {
              const who = schedule.interviewer_name_fa || schedule.interviewer_id || `مصاحبه‌گر ${idx + 1}`
              const dates = (schedule.dates || []).map((d) => formatDate(d) || d).filter(Boolean)
              const hours = [schedule.start_time, schedule.end_time].filter(Boolean).join(' تا ')
              return (
                <Row
                  key={`${who}-${idx}`}
                  label={who}
                  value={[dates.join('، '), hours].filter(Boolean).join(' — ')}
                />
              )
            })}
          </div>
        )
      })}
    </div>
  )
}

export default function SemesterPrepRecordedSummary({ entry }) {
  if (!shouldShowPrepRecordedSummary(entry)) return null
  const recorded = entry?.recorded && typeof entry.recorded === 'object' ? entry.recorded : {}
  const hasData = hasRecordedPrepData(recorded)

  return (
    <div className="semester-prep-recorded-summary" data-testid="semester-prep-recorded-summary">
      <h3 className="semester-prep-recorded-summary__title">خلاصهٔ اطلاعات ثبت‌شده</h3>
      {!hasData ? (
        <p className="muted" style={{ margin: 0, fontSize: '0.84rem' }}>
          هنوز اطلاعاتی ثبت نشده است.
        </p>
      ) : (
        <>
          {recorded.calendar ? (
            <Section title="تقویم آموزشی">
              <FieldRows rows={CALENDAR_FIELD_ROWS} data={recorded.calendar} />
              <Row label="تعطیلی پاییز" value={formatBreakPeriods(recorded.calendar.fall_break_periods)} />
              <Row label="تعطیلی زمستان" value={formatBreakPeriods(recorded.calendar.winter_break_periods)} />
            </Section>
          ) : null}

          {recorded.tuition ? (
            <Section title="شهریه و مصاحبه">
              <FieldRows rows={TUITION_FIELD_ROWS} data={recorded.tuition} />
            </Section>
          ) : null}

          {recorded.license ? (
            <Section title="پروانه فعالیت">
              <FieldRows rows={LICENSE_FIELD_ROWS} data={recorded.license} />
            </Section>
          ) : null}

          {recorded.courses ? (
            <Section title="دروس">
              {visibleCourseTables(recorded.courses).map((def) => (
                <CourseTable key={def.key} def={def} rows={recorded.courses[def.key]} />
              ))}
            </Section>
          ) : null}

          {recorded.marketing ? (
            <Section title="بازاریابی">
              <FieldRows rows={MARKETING_FIELD_ROWS} data={recorded.marketing} />
            </Section>
          ) : null}

          {recorded.interviews ? (
            <Section title="مصاحبه‌ها">
              <FieldRows
                rows={INTERVIEW_FIELD_ROWS}
                data={recorded.interviews}
                skipKeys={
                  recorded.interviews.interview_setup_plan
                    ? new Set(['comprehensive_interviewers', 'introductory_interviewers'])
                    : null
                }
              />
              <InterviewPlan plan={recorded.interviews.interview_setup_plan} />
            </Section>
          ) : null}
        </>
      )}
    </div>
  )
}
