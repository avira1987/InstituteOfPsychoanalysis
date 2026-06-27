import React from 'react'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

function formatRecipients(recipients) {
  const list = (recipients || []).filter(Boolean)
  if (!list.length) return 'مسئولان مربوط'
  if (list.length === 1) return list[0]
  if (list.length === 2) return `${list[0]} و ${list[1]}`
  return `${list.slice(0, -1).join('، ')} و ${list[list.length - 1]}`
}

/**
 * بنر مهلت تکمیل فرم مرحله — بالای «فرم این مرحله» در workbench آماده‌سازی ترم.
 * @param {{ deadlineAt?: string | null, overdue?: boolean, warningRecipientsFa?: string[] }} props
 */
export default function SemesterPrepStepDeadlineBanner({
  deadlineAt = null,
  overdue = false,
  warningRecipientsFa = [],
}) {
  if (!deadlineAt) return null

  const dateLabel = formatShamsiTehran(deadlineAt, { dateOnly: true })
  if (!dateLabel) return null

  const recipientsLabel = formatRecipients(warningRecipientsFa)
  const overdueStyle = overdue
    ? {
        background: '#fef2f2',
        border: '1px solid #fecaca',
        color: '#991b1b',
      }
    : {
        background: '#fffbeb',
        border: '1px solid #fcd34d',
        color: '#92400e',
      }

  const message = overdue
    ? `مهلت تکمیل این فرم (${dateLabel}) گذشته است — هرچه زودتر تکمیل کنید. در غیر این صورت (یا پس از آن) هشدار به ${recipientsLabel} ارسال می‌شود.`
    : `تا ${dateLabel} فرصت دارید این فرم را تکمیل کنید؛ در غیر این صورت هشدار به ${recipientsLabel} ارسال می‌شود.`

  return (
    <div
      data-testid="semester-prep-step-deadline-banner"
      style={{
        marginBottom: '0.85rem',
        padding: '0.7rem 0.9rem',
        borderRadius: '8px',
        fontSize: '0.84rem',
        lineHeight: 1.7,
        fontWeight: 600,
        ...overdueStyle,
      }}
    >
      {message}
    </div>
  )
}
