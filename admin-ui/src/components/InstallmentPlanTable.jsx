import React from 'react'
import { formatShamsiTehran } from '../utils/shamsiDateTime'
import { normalizeInstallmentPlan } from '../utils/installmentSchedulePreview'

function statusFa(status) {
  if (status === 'paid') return 'پرداخت‌شده'
  if (status === 'overdue') return 'معوق'
  return 'در انتظار'
}

export default function InstallmentPlanTable({ plan, compact = false, title = 'برنامهٔ اقساط' }) {
  const rows = normalizeInstallmentPlan(plan)
  if (!rows.length) return null
  return (
    <div
      className="installment-plan-table"
      data-testid="installment-plan-table"
      style={{ marginTop: compact ? '0.45rem' : '0.65rem' }}
    >
      {title ? (
        <div className="installment-plan-table__title">
          {title}
        </div>
      ) : null}
      <div style={{ overflowX: 'auto' }}>
        <table className="data-table" style={{ width: '100%', fontSize: compact ? '0.78rem' : '0.84rem', margin: 0 }}>
          <thead>
            <tr>
              <th>قسط</th>
              <th>مبلغ</th>
              <th>سررسید</th>
              <th>وضعیت</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const idx = Number(row.index || 0)
              const rial = Number(row.amount_rial || 0)
              return (
                <tr key={idx || row.due_at}>
                  <td>{idx ? idx.toLocaleString('fa-IR') : '—'}</td>
                  <td>{Number.isFinite(rial) ? `${Math.round(rial / 10).toLocaleString('fa-IR')} تومان` : '—'}</td>
                  <td>{formatShamsiTehran(row.due_at, { dateOnly: true })}</td>
                  <td>{statusFa(row.status)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
