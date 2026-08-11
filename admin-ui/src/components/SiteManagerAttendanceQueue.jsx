import React, { useMemo } from 'react'
import { formatStudentCodeDisplay, labelProcess, labelState } from '../utils/processDisplay'

const ATTENDANCE_PROCESS_CODES = new Set([
  'attendance_tracking',
  'unannounced_absence_reaction',
  'unannounced_supervision_absence_reaction',
])

function isAttendanceFollowupItem(item) {
  if (!item || item.kind === 'readiness') return false
  const code = (item.process_code || '').toLowerCase()
  const state = (item.state_code || item.current_state || '').toLowerCase()
  if (ATTENDANCE_PROCESS_CODES.has(code)) return true
  return code.includes('attendance') || code.includes('absence')
    || state.includes('attendance') || state.includes('absence')
}

/**
 * صف فشردهٔ حضور درمان برای مسئول سایت — از my-operator-followup (بدون N+1).
 */
export default function SiteManagerAttendanceQueue({
  items = [],
  selectedInstanceId,
  onOpenInstance,
  compact = false,
}) {
  const queue = useMemo(
    () => (items || []).filter(isAttendanceFollowupItem),
    [items],
  )

  if (!queue.length) {
    return (
      <div className="empty-state" style={{ padding: compact ? '1.5rem' : '3rem' }}>
        <div style={{ fontSize: compact ? '2rem' : '3rem', marginBottom: '0.5rem' }}>✅</div>
        <p>مورد حضور/غیاب در صف پیگیری نیست.</p>
      </div>
    )
  }

  return (
    <div
      data-testid="site-manager-attendance-queue"
      style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}
    >
      {queue.map((item) => {
        const instanceId = item.instance_id || item.id
        const selected = selectedInstanceId === instanceId
        return (
          <button
            key={instanceId}
            type="button"
            data-testid={`attendance-queue-${instanceId}`}
            onClick={() => onOpenInstance?.(instanceId)}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: '0.5rem',
              padding: '0.75rem 1rem',
              borderRadius: '8px',
              cursor: 'pointer',
              textAlign: 'right',
              border: selected ? '2px solid var(--danger)' : '1px solid #fca5a5',
              background: selected ? 'var(--danger-light, #fef2f2)' : '#fff',
            }}
          >
            <div style={{ minWidth: 0 }}>
              <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                {labelProcess(item.process_code)}
              </div>
              <div style={{ fontSize: '0.75rem', color: '#6b7280', marginTop: '0.15rem' }}>
                دانشجو: {formatStudentCodeDisplay(item.student_code)}
                {' · '}
                {labelState(item.state_code || item.current_state)}
              </div>
              {item.responsible_role_label_fa && (
                <div style={{ fontSize: '0.72rem', color: '#94a3b8', marginTop: '0.1rem' }}>
                  نقش مسئول: {item.responsible_role_label_fa}
                </div>
              )}
            </div>
            <span className="badge badge-danger" style={{ fontSize: '0.7rem', flexShrink: 0 }}>
              باز کردن
            </span>
          </button>
        )
      })}
    </div>
  )
}

export { isAttendanceFollowupItem }
