import React, { useEffect, useState } from 'react'
import { processExecApi, studentApi } from '../services/api'
import { labelState } from '../utils/processDisplay'

function normalizeRows(raw) {
  if (!Array.isArray(raw)) return []
  return raw
    .filter((r) => r && typeof r === 'object')
    .map((r) => ({
      patient_label: String(r.patient_label || r.patient_name || '').trim(),
      assigned_therapist_user_id: String(r.assigned_therapist_user_id || r.therapist_user_id || '').trim(),
    }))
    .filter((r) => r.patient_label)
}

const ACCENT = '#0f766e'
const ACCENT_BG = '#f0fdfa'
const HINTS = {
  referral_triggered: 'لیست بیماران انترن را وارد کنید و «ثبت لیست» را بزنید.',
  patients_listed: 'برای هر بیمار درمانگر جایگزین را انتخاب و «ثبت تخصیص» را بزنید.',
  therapists_assigned: 'اطلاع به دانشجو و درمانگران تخصیص‌شده را ارسال کنید؛ پرونده پس از ارسال بسته می‌شود.',
  notifications_sent: 'اطلاع ارسال شد؛ پرونده در حال بسته شدن است.',
  closed: 'ارجاع مختومه شد.',
}

/**
 * کارتابل کمیته نظارت — هاب ارجاع بیمار (patient_referral)، نه intern_bulk.
 */
export default function PatientReferralHubPanel({
  detail = null,
  availableTransitions = [],
  instanceId = null,
  showToast,
  onRefreshInstance,
  active = true,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const [rows, setRows] = useState([])
  const [therapists, setTherapists] = useState([])
  const [busy, setBusy] = useState(false)

  const isHub = detail?.process_code === 'patient_referral'

  useEffect(() => {
    setRows(normalizeRows(ctx.referral_patients).length
      ? normalizeRows(ctx.referral_patients)
      : [{ patient_label: '', assigned_therapist_user_id: '' }])
  }, [ctx.referral_patients, currentState])

  useEffect(() => {
    if (!active || !isHub) return
    studentApi.therapists().then((res) => {
      setTherapists(Array.isArray(res.data) ? res.data : [])
    }).catch(() => setTherapists([]))
  }, [active, isHub])

  const canList = availableTransitions.some((t) => t.trigger_event === 'list_submitted')
  const canAssign = availableTransitions.some((t) => t.trigger_event === 'assignments_done')
  const canNotify = availableTransitions.some((t) => t.trigger_event === 'notifications_done')

  const updateRow = (idx, patch) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)))
  }

  const fire = async (trigger, payload) => {
    const id = instanceId || detail?.id
    if (!id) return
    setBusy(true)
    try {
      const res = await processExecApi.trigger(id, { trigger_event: trigger, payload })
      if (res.data?.success) {
        showToast?.('ثبت شد')
        await onRefreshInstance?.(id)
      } else {
        showToast?.(res.data?.error || 'انجام نشد', 'error')
      }
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : (e.message || 'خطا'), 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!active || !detail || !isHub) return null

  const payloadRows = rows
    .map((r) => ({
      patient_label: String(r.patient_label || '').trim(),
      assigned_therapist_user_id: String(r.assigned_therapist_user_id || '').trim() || null,
    }))
    .filter((r) => r.patient_label)

  return (
    <div
      className="card"
      data-testid="patient-referral-hub-panel"
      style={{ marginBottom: '1.25rem' }}
    >
      <div className="card-header">
        <h3 className="card-title">ارجاع بیماران انترن (هاب)</h3>
        {currentState && (
          <span className="badge badge-info" style={{ fontSize: '0.78rem' }}>
            {labelState(currentState)}
          </span>
        )}
      </div>
      <div style={{ padding: '0 1rem 1rem' }}>
        <p
          data-testid="patient-referral-hub-hint"
          style={{
            padding: '0.75rem 1rem',
            borderRadius: '10px',
            background: ACCENT_BG,
            borderRight: `4px solid ${ACCENT}`,
            fontSize: '0.86rem',
            lineHeight: 1.7,
            color: '#115e59',
          }}
        >
          {HINTS[currentState] || 'پرونده ارجاع بیماران انترن.'}
        </p>
        {(ctx.source_process_code || ctx.source_reason) && (
          <p style={{ fontSize: '0.82rem', color: '#64748b' }}>
            مبدأ: {ctx.source_process_code || '—'}
            {ctx.source_reason ? ` — ${ctx.source_reason}` : ''}
            {ctx.leave_terms != null ? ` — ${ctx.leave_terms} ترم` : ''}
          </p>
        )}

        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.84rem', marginTop: '0.65rem' }}>
          <thead>
            <tr style={{ background: '#f1f5f9', textAlign: 'right' }}>
              <th style={{ padding: '0.4rem' }}>بیمار</th>
              <th style={{ padding: '0.4rem' }}>درمانگر جایگزین</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => (
              <tr key={idx}>
                <td style={{ padding: '0.35rem' }}>
                  <input
                    data-testid={`patient-referral-label-${idx}`}
                    className="form-control"
                    value={row.patient_label || ''}
                    disabled={!canList && !canAssign}
                    onChange={(e) => updateRow(idx, { patient_label: e.target.value })}
                  />
                </td>
                <td style={{ padding: '0.35rem' }}>
                  <select
                    data-testid={`patient-referral-therapist-${idx}`}
                    className="form-control"
                    value={row.assigned_therapist_user_id || ''}
                    disabled={!canAssign}
                    onChange={(e) => updateRow(idx, { assigned_therapist_user_id: e.target.value })}
                  >
                    <option value="">— انتخاب —</option>
                    {therapists.map((t) => (
                      <option key={t.id} value={t.id}>{t.label_fa || t.id}</option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {canList && (
          <button
            type="button"
            className="btn btn-outline btn-sm"
            style={{ marginTop: '0.4rem' }}
            onClick={() => setRows((prev) => [...prev, { patient_label: '', assigned_therapist_user_id: '' }])}
          >
            افزودن ردیف
          </button>
        )}

        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.75rem' }}>
          {canList && (
            <button
              type="button"
              className="btn btn-primary"
              data-testid="patient-referral-submit-list"
              disabled={busy || payloadRows.length < 1}
              onClick={() => fire('list_submitted', { referral_patients: payloadRows })}
            >
              ثبت لیست
            </button>
          )}
          {canAssign && (
            <button
              type="button"
              className="btn btn-primary"
              data-testid="patient-referral-submit-assign"
              disabled={busy || payloadRows.some((r) => !r.assigned_therapist_user_id)}
              onClick={() => fire('assignments_done', { referral_patients: payloadRows })}
            >
              ثبت تخصیص
            </button>
          )}
          {canNotify && (
            <button
              type="button"
              className="btn btn-primary"
              data-testid="patient-referral-submit-notify"
              disabled={busy}
              onClick={() => fire('notifications_done', {})}
            >
              ارسال اطلاع و بستن
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
