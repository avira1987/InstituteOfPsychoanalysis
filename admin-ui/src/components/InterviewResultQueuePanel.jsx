import React, { useCallback, useEffect, useState } from 'react'
import { interviewSlotsApi, processExecApi } from '../services/api'
import { labelProcess, labelState } from '../utils/processDisplay'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

function roleBadge(item) {
  const parts = []
  if (item.is_slot_creator) parts.push('ایجادکنندهٔ وقت')
  if (item.is_assigned_interviewer) parts.push('مصاحبه‌گر')
  return parts.length ? parts.join(' · ') : '—'
}

/**
 * فهرست پرونده‌های مصاحبه برای ثبت برگزاری / ثبت نتیجه در تب ثبت نتیجه.
 */
export default function InterviewResultQueuePanel({
  showToast,
  onOpenResult,
  onAfterAction,
}) {
  const [items, setItems] = useState([])
  const [includePast, setIncludePast] = useState(false)
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState(null)

  const load = useCallback(() => {
    setLoading(true)
    interviewSlotsApi
      .resultQueue(includePast)
      .then((r) => setItems(r.data?.items || []))
      .catch(() => {
        setItems([])
        showToast?.('بارگذاری فهرست ثبت نتیجه ناموفق بود.', 'error')
      })
      .finally(() => setLoading(false))
  }, [includePast, showToast])

  useEffect(() => {
    load()
  }, [load])

  const advanceInterview = async (instanceId) => {
    if (!instanceId) return
    setBusyId(instanceId)
    try {
      const res = await processExecApi.trigger(instanceId, {
        trigger_event: 'interview_time_reached',
        payload: {},
      })
      if (res.data?.success) {
        showToast?.(`مرحله به «${labelState(res.data.to_state)}» رفت`)
        load()
        onAfterAction?.()
      } else {
        showToast?.(res.data?.error || 'انتقال انجام نشد', 'error')
      }
    } catch (e) {
      const d = e.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ثبت برگزاری مصاحبه', 'error')
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="card" style={{ marginBottom: '1.5rem' }} data-testid="interview-result-queue">
      <div className="card-header">
        <h3 className="card-title">فهرست ثبت نتیجهٔ مصاحبه</h3>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', maxWidth: '48rem', lineHeight: 1.6 }}>
          پرونده‌هایی که شما وقت مصاحبهٔ آن‌ها را ساخته‌اید یا به‌عنوان مصاحبه‌گر اختصاص دارید.
          ابتدا در صورت نیاز «ثبت برگزاری» را بزنید، سپس «ثبت نتیجه» را انتخاب کنید.
        </p>
      </div>
      <div style={{ padding: '0 1.25rem 1.25rem' }}>
        <label style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.88rem', marginBottom: '0.75rem' }}>
          <input type="checkbox" checked={includePast} onChange={(e) => setIncludePast(e.target.checked)} />
          نمایش گذشته
        </label>
        {loading ? (
          <p className="muted">در حال بارگذاری…</p>
        ) : !items.length ? (
          <div
            className="empty-state"
            style={{ padding: '1rem', background: 'var(--bg)', borderRadius: '8px', fontSize: '0.9rem', lineHeight: 1.65 }}
          >
            <p style={{ margin: 0 }}>
              پرونده‌ای برای ثبت نتیجه در صف شما نیست.
              {!includePast && ' اگر مصاحبه گذشته است، «نمایش گذشته» را فعال کنید.'}
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', fontSize: '0.88rem' }}>
              <thead>
                <tr>
                  <th>زمان مصاحبه</th>
                  <th>دانشجو</th>
                  <th>کد</th>
                  <th>فرایند</th>
                  <th>وضعیت</th>
                  <th>نقش شما</th>
                  <th>اقدام</th>
                </tr>
              </thead>
              <tbody>
                {items.map((row) => {
                  const busy = busyId === row.instance_id
                  return (
                    <tr key={row.instance_id}>
                      <td>{formatShamsiTehran(row.slot_starts_at)}</td>
                      <td>{row.student_name_fa || '—'}</td>
                      <td>{row.student_code || '—'}</td>
                      <td>{labelProcess(row.process_code)}</td>
                      <td>{labelState(row.current_state)}</td>
                      <td style={{ fontSize: '0.8rem' }}>{roleBadge(row)}</td>
                      <td style={{ whiteSpace: 'nowrap' }}>
                        {row.can_advance ? (
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            disabled={busy}
                            data-testid={`queue-advance-${row.instance_id}`}
                            onClick={() => advanceInterview(row.instance_id)}
                          >
                            {busy ? 'در حال ثبت…' : 'ثبت برگزاری'}
                          </button>
                        ) : null}
                        {row.can_submit_result ? (
                          <button
                            type="button"
                            className="btn btn-secondary btn-sm"
                            data-testid={`queue-result-${row.instance_id}`}
                            style={row.can_advance ? { marginTop: '0.35rem' } : undefined}
                            onClick={() => onOpenResult?.(row.instance_id)}
                          >
                            ثبت نتیجه
                          </button>
                        ) : null}
                        {!row.can_advance && !row.can_submit_result ? '—' : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
