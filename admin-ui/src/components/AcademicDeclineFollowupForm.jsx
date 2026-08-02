import React, { useEffect, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'
import { resolveDeclineFollowupRows } from '../utils/termEndTranscriptRows'

/**
 * Checklist پیگیری افت تحصیلی — فرایند ۳۲، state followup_in_progress.
 */
export default function AcademicDeclineFollowupForm({
  detail = null,
  user = null,
  onUpdated = null,
  showToast = null,
}) {
  const ctx = detail?.context_data || {}
  const instanceId = detail?.instance_id || detail?.id

  const initialRows = useMemo(
    () => resolveDeclineFollowupRows(ctx),
    [ctx.decline_followup_rows, ctx.failed_courses],
  )

  const [rows, setRows] = useState(initialRows)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setRows(initialRows)
  }, [initialRows])

  if (
    !detail
    || detail.process_code !== 'introductory_term_end'
    || detail.current_state !== 'followup_in_progress'
    || !instanceId
  ) {
    return null
  }

  const toggleRow = (idx) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, followup_done: !r.followup_done } : r)))
  }

  const allDone = rows.length > 0 && rows.every((r) => r.followup_done)

  const saveAndComplete = async () => {
    if (!allDone) {
      showToast?.('لطفاً برای همهٔ ردیف‌ها تیک «پیگیری انجام شد» را بزنید.', 'error')
      return
    }
    setBusy(true)
    try {
      await processExecApi.registerOperatorStepForms(instanceId, {
        form_values: {
          academic_decline_followup_form: rows,
          decline_followup_rows: rows,
        },
        state_code: 'followup_in_progress',
      })
      const triggerRes = await processExecApi.trigger(instanceId, {
        trigger_event: 'all_followups_done',
      })
      if (triggerRes.data?.success === false) {
        showToast?.(triggerRes.data?.message || 'ثبت شد ولی پیشروی انجام نشد.', 'error')
      } else {
        showToast?.('پیگیری افت تحصیلی ثبت و فرایند تکمیل شد.')
      }
      onUpdated?.()
    } catch (e) {
      const d = e?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ثبت پیگیری', 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!rows.length) {
    return (
      <div
        data-testid="academic-decline-followup-empty"
        className="muted"
        style={{ marginBottom: '1rem', fontSize: '0.85rem' }}
      >
        ردیفی برای پیگیری افت تحصیلی در context ثبت نشده است.
      </div>
    )
  }

  return (
    <div
      data-testid="academic-decline-followup-form"
      style={{
        marginBottom: '1.25rem',
        padding: '1rem 1.15rem',
        borderRadius: '10px',
        border: '1px solid #fcd34d',
        background: '#fffbeb',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.75rem', color: '#92400e' }}>
        فرم پیگیری تماس (افت تحصیلی)
      </h4>
      <table className="data-table" style={{ width: '100%', fontSize: '0.84rem', marginBottom: '0.85rem' }}>
        <thead>
          <tr>
            <th>نام دانشجو</th>
            <th>تماس</th>
            <th>دروس مردود</th>
            <th>پیگیری انجام شد</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={idx}>
              <td>{row.student_name || '—'}</td>
              <td>{row.student_phone || '—'}</td>
              <td>{row.failed_courses || '—'}</td>
              <td>
                <input
                  type="checkbox"
                  checked={!!row.followup_done}
                  onChange={() => toggleRow(idx)}
                  disabled={busy || (user?.role !== 'admissions_officer' && user?.role !== 'admin' && user?.role !== 'staff')}
                  data-testid={`followup-done-${idx}`}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <button
        type="button"
        className="btn btn-primary btn-sm"
        disabled={busy || !allDone}
        onClick={saveAndComplete}
        data-testid="academic-decline-followup-submit"
      >
        {busy ? 'در حال ثبت…' : 'ثبت پیگیری‌ها و تکمیل فرایند'}
      </button>
    </div>
  )
}
