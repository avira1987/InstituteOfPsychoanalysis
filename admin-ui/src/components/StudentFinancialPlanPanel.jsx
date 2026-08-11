import React, { useCallback, useEffect, useState } from 'react'
import { studentApi } from '../services/api'
import SepPaymentPanel from './SepPaymentPanel'
import { PROCESS_LABELS_FA } from '../utils/processMetadataLabels'

function fmtTomanFromRial(rial) {
  if (rial == null) return '—'
  try {
    return `${Math.round(Number(rial) / 10).toLocaleString('fa-IR')} تومان`
  } catch {
    return '—'
  }
}

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso.length <= 10 ? `${iso}T12:00:00` : iso).toLocaleDateString('fa-IR')
  } catch {
    return String(iso)
  }
}

function statusLabel(status) {
  if (status === 'paid') return 'پرداخت‌شده'
  if (status === 'overdue') return 'معوق'
  return 'در انتظار'
}

function processLabel(code) {
  return PROCESS_LABELS_FA?.[code] || code || '—'
}

export default function StudentFinancialPlanPanel({ studentId, active = true }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    if (!active) return
    setLoading(true)
    setError(null)
    try {
      const res = await studentApi.myFinance()
      setData(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'خطا در بارگذاری اطلاعات مالی')
    } finally {
      setLoading(false)
    }
  }, [active])

  useEffect(() => {
    load()
  }, [load])

  if (!active) return null

  const balance = data?.balance || {}
  const installments = data?.installments || []
  const ledger = data?.ledger || []
  const openPayments = data?.open_payments || []

  return (
    <div className="card" data-testid="student-financial-plan-panel">
      <div className="card-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.75rem' }}>
        <h3 className="card-title">پلن مالی و اقساط</h3>
        <button type="button" className="btn btn-secondary btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'بروزرسانی'}
        </button>
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        {error && (
          <div className="alert alert-danger" style={{ marginBottom: '0.75rem' }}>{error}</div>
        )}

        {data && (
          <>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                gap: '0.65rem',
                marginBottom: '1rem',
              }}
            >
              <SummaryTile label="بدهی" value={`${Number(balance.total_debt || 0).toLocaleString('fa-IR')} تومان`} tone="#b45309" />
              <SummaryTile label="پرداخت‌شده" value={`${Number(balance.total_paid || 0).toLocaleString('fa-IR')} تومان`} tone="#16a34a" />
              <SummaryTile label="اعتبار" value={`${Number(balance.total_credit || 0).toLocaleString('fa-IR')} تومان`} tone="#2563eb" />
              <SummaryTile label="مانده" value={`${Number(balance.net_balance || 0).toLocaleString('fa-IR')} تومان`} tone="#7c3aed" />
            </div>

            {openPayments.length > 0 && (
              <section style={{ marginBottom: '1rem' }}>
                <h4 style={{ fontSize: '0.95rem', margin: '0 0 0.5rem' }}>پرداخت قسط جاری</h4>
                {openPayments.map((op) => (
                  <div
                    key={op.instance_id}
                    style={{
                      padding: '0.75rem',
                      borderRadius: '8px',
                      background: '#fffbeb',
                      borderRight: '4px solid #d97706',
                      marginBottom: '0.65rem',
                    }}
                  >
                    <p style={{ margin: '0 0 0.35rem', fontSize: '0.88rem' }}>
                      {processLabel(op.process_code)}
                      {op.current_installment_index != null && (
                        <span> · قسط {Number(op.current_installment_index).toLocaleString('fa-IR')}</span>
                      )}
                    </p>
                    <p style={{ margin: '0 0 0.5rem', fontWeight: 600 }}>
                      مبلغ قابل پرداخت: {fmtTomanFromRial(op.payable_amount_rial)}
                      {op.next_installment_due_at && (
                        <span style={{ fontWeight: 400, fontSize: '0.85rem', color: '#64748b' }}>
                          {' '}· سررسید: {fmtDate(op.next_installment_due_at)}
                        </span>
                      )}
                    </p>
                    {studentId && op.instance_id && (
                      <SepPaymentPanel
                        instanceId={op.instance_id}
                        studentId={studentId}
                        amountRial={Number(op.payable_amount_rial)}
                        description={`پرداخت قسط شهریه — ${processLabel(op.process_code)}`}
                      />
                    )}
                  </div>
                ))}
              </section>
            )}

            {installments.length > 0 && (
              <section style={{ marginBottom: '1rem' }}>
                <h4 style={{ fontSize: '0.95rem', margin: '0 0 0.5rem' }}>برنامه اقساط</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table className="table" style={{ fontSize: '0.85rem', width: '100%' }}>
                    <thead>
                      <tr>
                        <th>فرایند</th>
                        <th>قسط</th>
                        <th>مبلغ</th>
                        <th>سررسید</th>
                        <th>وضعیت</th>
                      </tr>
                    </thead>
                    <tbody>
                      {installments.map((row, i) => (
                        <tr key={`${row.instance_id}-${row.index}-${i}`}>
                          <td>{processLabel(row.process_code)}</td>
                          <td>{row.index != null ? Number(row.index).toLocaleString('fa-IR') : '—'}</td>
                          <td>{fmtTomanFromRial(row.amount_rial)}</td>
                          <td>{fmtDate(row.due_at)}</td>
                          <td>{statusLabel(row.status)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {ledger.length > 0 && (
              <section>
                <h4 style={{ fontSize: '0.95rem', margin: '0 0 0.5rem' }}>گردش حساب</h4>
                <div style={{ overflowX: 'auto' }}>
                  <table className="table" style={{ fontSize: '0.85rem', width: '100%' }}>
                    <thead>
                      <tr>
                        <th>تاریخ</th>
                        <th>نوع</th>
                        <th>مبلغ (تومان)</th>
                        <th>شرح</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ledger.map((row) => (
                        <tr key={row.id}>
                          <td>{fmtDate(row.created_at)}</td>
                          <td>{ledgerTypeLabel(row.record_type)}</td>
                          <td>{Number(row.amount || 0).toLocaleString('fa-IR')}</td>
                          <td>{row.description_fa || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>
            )}

            {!installments.length && !ledger.length && !openPayments.length && (
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                هنوز رکورد مالی شهریه‌ای ثبت نشده است.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function SummaryTile({ label, value, tone }) {
  return (
    <div style={{ padding: '0.65rem 0.75rem', borderRadius: '8px', background: '#f8fafc', borderRight: `3px solid ${tone}` }}>
      <div style={{ fontSize: '0.75rem', color: '#64748b', marginBottom: '0.2rem' }}>{label}</div>
      <div style={{ fontWeight: 600, fontSize: '0.9rem', color: tone }}>{value}</div>
    </div>
  )
}

function ledgerTypeLabel(type) {
  const map = {
    payment: 'پرداخت',
    debt: 'بدهی',
    credit: 'اعتبار',
    absence_fee: 'جریمه غیبت',
  }
  return map[type] || type || '—'
}
