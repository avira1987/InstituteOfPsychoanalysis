import React from 'react'
import { labelProcess, labelState } from '../utils/processDisplay'
import { assignedRoleLabelFa } from '../utils/operatorProcessGuidance'

/**
 * نوار خلاصهٔ نقش‌محور: دانشجو، فرایند، مرحله، نقش مسئول، اقدام لازم.
 */
export default function OperatorCaseFactsSummary({
  instanceDetail,
  guidance,
  studentCode,
  studentNameFa,
}) {
  if (!instanceDetail) return null

  const code = studentCode || instanceDetail.student_code
  const name = studentNameFa || instanceDetail.student_name_fa
  const studentParts = [name, code].filter(Boolean)
  const studentLabel = studentParts.length ? studentParts.join(' — ') : '—'

  const processLabel = labelProcess(instanceDetail.process_code)
  const stageLabel = guidance?.shortFa || labelState(instanceDetail.current_state)
  const roleLabel = guidance?.waitingRoleLabelFa
    || (guidance?.role ? assignedRoleLabelFa(guidance.role) : '')
  const actionLabel = (guidance?.taskFa || '').trim()

  const facts = [
    { label: 'دانشجو', value: studentLabel },
    { label: 'فرایند', value: processLabel },
    { label: 'مرحله', value: stageLabel },
    roleLabel ? { label: 'نقش مسئول', value: roleLabel } : null,
    actionLabel ? { label: 'اقدام لازم', value: actionLabel } : null,
  ].filter(Boolean)

  return (
    <div
      data-testid="operator-case-facts-summary"
      style={{
        marginBottom: '1rem',
        border: '1px solid #c7d2fe',
        borderRadius: '10px',
        background: 'linear-gradient(180deg, #eef2ff 0%, #f8fafc 100%)',
        overflow: 'hidden',
      }}
    >
      {facts.map(({ label, value }, idx) => (
        <div
          key={label}
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(100px, 28%) 1fr',
            gap: '0.65rem',
            padding: '0.65rem 0.85rem',
            borderBottom: idx < facts.length - 1 ? '1px solid #e0e7ff' : 'none',
            fontSize: '0.82rem',
            alignItems: 'start',
          }}
        >
          <div style={{ color: '#4338ca', fontWeight: 700 }}>{label}</div>
          <div style={{ color: '#1e293b', lineHeight: 1.55, wordBreak: 'break-word' }}>{value}</div>
        </div>
      ))}
    </div>
  )
}
