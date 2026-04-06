import React, { useState, useEffect, useCallback } from 'react'
import { financeApi } from '../services/api'

const TYPE_LABELS = {
  payment: 'پرداخت',
  credit: 'بستانکاری / استرداد',
  debt: 'بدهی',
  absence_fee: 'جریمه غیبت',
}

function fmtMoney(n) {
  if (n == null || Number.isNaN(n)) return '—'
  return Math.round(n).toLocaleString('fa-IR')
}

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('fa-IR', { dateStyle: 'short', timeStyle: 'short' })
  } catch {
    return iso
  }
}

export default function FinancialDashboard() {
  const [summary, setSummary] = useState(null)
  const [ctx, setCtx] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(null)
  const [exporting, setExporting] = useState(false)

  const [balData, setBalData] = useState(null)
  const [balPage, setBalPage] = useState(1)
  const [balSort, setBalSort] = useState('balance_asc')
  const [balDebtorsOnly, setBalDebtorsOnly] = useState(false)
  const [balLoading, setBalLoading] = useState(false)

  const [txData, setTxData] = useState(null)
  const [txPage, setTxPage] = useState(1)
  const [txType, setTxType] = useState('')
  const [txQ, setTxQ] = useState('')
  const [txQDebounced, setTxQDebounced] = useState('')
  const [txLoading, setTxLoading] = useState(false)

  const loadCore = useCallback(() => {
    setErr(null)
    return Promise.all([
      financeApi.summary().then((r) => setSummary(r.data)),
      financeApi.context().then((r) => setCtx(r.data)).catch(() => setCtx(null)),
    ])
  }, [])

  useEffect(() => {
    setLoading(true)
    loadCore()
      .catch((e) => setErr(e.response?.data?.detail || e.message))
      .finally(() => setLoading(false))
  }, [loadCore])

  useEffect(() => {
    const t = setTimeout(() => setTxQDebounced(txQ.trim()), 400)
    return () => clearTimeout(t)
  }, [txQ])

  useEffect(() => {
    setBalLoading(true)
    financeApi
      .studentBalances({
        page: balPage,
        page_size: 25,
        sort: balSort,
        only_debtors: balDebtorsOnly,
      })
      .then((r) => setBalData(r.data))
      .catch((e) => setErr(e.response?.data?.detail || e.message))
      .finally(() => setBalLoading(false))
  }, [balPage, balSort, balDebtorsOnly])

  useEffect(() => {
    setTxLoading(true)
    financeApi
      .transactions({
        page: txPage,
        page_size: 20,
        record_type: txType || undefined,
        q: txQDebounced || undefined,
      })
      .then((r) => setTxData(r.data))
      .catch((e) => setErr(e.response?.data?.detail || e.message))
      .finally(() => setTxLoading(false))
  }, [txPage, txType, txQDebounced])

  const handleExport = async () => {
    setExporting(true)
    try {
      await financeApi.exportCsv()
    } catch (e) {
      setErr(e.message || 'خطا در خروجی')
    } finally {
      setExporting(false)
    }
  }

  if (loading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', padding: '4rem' }}>
        <div className="loading-spinner" />
      </div>
    )
  }

  const breakdown = summary?.breakdown || {}
  const breakdownRows = Object.entries(breakdown).sort((a, b) =>
    (TYPE_LABELS[a[0]] || a[0]).localeCompare(TYPE_LABELS[b[0]] || b[0], 'fa'),
  )

  const paginate = (page, pages, setPage) => (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginTop: '1rem', flexWrap: 'wrap' }}>
      <button type="button" className="btn btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
        قبلی
      </button>
      <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
        صفحه {page?.toLocaleString('fa-IR')} از {pages?.toLocaleString('fa-IR')}
      </span>
      <button
        type="button"
        className="btn btn-outline btn-sm"
        disabled={page >= pages}
        onClick={() => setPage((p) => p + 1)}
      >
        بعدی
      </button>
    </div>
  )

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">داشبورد مالی</h1>
          <p className="page-subtitle">
            بررسی تراکنش‌ها، بدهی و بستانکاری، مانده دانشجویان و هم‌ترازی با حسابداری مراکز آموزشی — دسترسی فقط برای نقش
            اپراتور مالی (مدیر سیستم به‌صورت سرپرست)
          </p>
        </div>
      </div>

      {err && (
        <div className="card" style={{ borderColor: '#fca5a5', background: '#fef2f2', marginBottom: '1rem' }}>
          {err}
        </div>
      )}

      <div className="stats-grid" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <div className="stat-icon success">💰</div>
          <div>
            <div className="stat-value">{summary ? fmtMoney(summary.total_payments) : '—'}</div>
            <div className="stat-label">جمع پرداخت‌ها (تومان)</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon info">↩️</div>
          <div>
            <div className="stat-value">{summary ? fmtMoney(summary.total_credits) : '—'}</div>
            <div className="stat-label">بستانکاری / استرداد</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon warning">📉</div>
          <div>
            <div className="stat-value">{summary ? fmtMoney(summary.total_debts) : '—'}</div>
            <div className="stat-label">بدهی و جریمه</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon primary">📄</div>
          <div>
            <div className="stat-value">{summary?.record_count ?? '—'}</div>
            <div className="stat-label">تعداد رکورد مالی</div>
          </div>
        </div>
      </div>

      {ctx && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h3 className="card-title">{ctx.title}</h3>
          </div>
          <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.95rem', lineHeight: 1.7 }}>{ctx.intro}</p>
          {(ctx.sections || []).map((sec) => (
            <div key={sec.heading} style={{ marginBottom: '1.25rem' }}>
              <h4 style={{ fontSize: '1rem', marginBottom: '0.5rem' }}>{sec.heading}</h4>
              <ul style={{ margin: 0, paddingRight: '1.25rem', color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.75 }}>
                {(sec.items || []).map((it) => (
                  <li key={it}>{it}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}

      {summary && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h3 className="card-title">معادلات و شاخص‌های مالی</h3>
          </div>
          <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            بر اساس رکوردهای ثبت‌شده؛ برای سند رسمی با حسابدار مرکز هماهنگ کنید.
          </p>

          <div
            style={{
              display: 'grid',
              gap: '1rem',
              gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            }}
          >
            <div
              style={{
                padding: '1rem',
                borderRadius: '8px',
                border: '1px solid var(--border-color, #e5e7eb)',
                background: 'var(--bg-secondary, #f9fafb)',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.95rem' }}>خالص نقد پس از استرداد</div>
              <code style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                پرداخت‌ها − بستانکاری استردادی
              </code>
              <div style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                {fmtMoney(summary.net_cash_after_credits)} <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>تومان</span>
              </div>
            </div>

            <div
              style={{
                padding: '1rem',
                borderRadius: '8px',
                border: '1px solid var(--border-color, #e5e7eb)',
                background: 'var(--bg-secondary, #f9fafb)',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.95rem' }}>تفاضل نسبت به بدهی‌های ثبت‌شده</div>
              <code style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                (خالص نقد پس از استرداد) − (بدهی + جریمه)
              </code>
              <div style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                {fmtMoney(summary.net_vs_charges)} <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>تومان</span>
              </div>
            </div>

            <div
              style={{
                padding: '1rem',
                borderRadius: '8px',
                border: '1px solid var(--border-color, #e5e7eb)',
                background: 'var(--bg-secondary, #f9fafb)',
              }}
            >
              <div style={{ fontWeight: 600, marginBottom: '0.5rem', fontSize: '0.95rem' }}>میانگین مبلغ هر رکورد پرداخت</div>
              <code style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.75rem', color: 'var(--text-secondary)' }}>
                جمع پرداخت‌ها ÷ تعداد رکوردهای نوع «پرداخت»
              </code>
              <div style={{ fontSize: '1.35rem', fontWeight: 700 }}>
                {summary.avg_payment != null ? fmtMoney(summary.avg_payment) : '—'}{' '}
                <span style={{ fontSize: '0.85rem', fontWeight: 500 }}>تومان</span>
              </div>
            </div>
          </div>
        </div>
      )}

      {summary && breakdownRows.length > 0 && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <div className="card-header">
            <h3 className="card-title">تفکیک بر اساس نوع رکورد</h3>
          </div>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>نوع</th>
                  <th style={{ textAlign: 'left' }}>تعداد</th>
                  <th style={{ textAlign: 'left' }}>جمع مبلغ (تومان)</th>
                </tr>
              </thead>
              <tbody>
                {breakdownRows.map(([key, v]) => (
                  <tr key={key}>
                    <td>{TYPE_LABELS[key] || key}</td>
                    <td style={{ textAlign: 'left' }}>{v.count?.toLocaleString('fa-IR') ?? '—'}</td>
                    <td style={{ textAlign: 'left' }}>{fmtMoney(v.sum)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h3 className="card-title">مانده مالی دانشجویان (بدهی / بستانکاری)</h3>
        </div>
        <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          مانده = (پرداخت‌ها + بستانکاری) − (بدهی + جریمه). مانده منفی یعنی مطالبه بیش از وصول؛ مثبت یعنی پیش‌پرداخت یا طلب دانشجو.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0 }}>
            <label className="form-label">مرتب‌سازی</label>
            <select className="form-input" value={balSort} onChange={(e) => { setBalPage(1); setBalSort(e.target.value) }}>
              <option value="balance_asc">مانده: بیشترین بدهی اول</option>
              <option value="balance_desc">مانده: بیشترین طلب اول</option>
              <option value="code_asc">کد دانشجویی</option>
            </select>
          </div>
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={balDebtorsOnly}
              onChange={(e) => {
                setBalPage(1)
                setBalDebtorsOnly(e.target.checked)
              }}
            />
            فقط بدهکاران (مانده منفی)
          </label>
        </div>
        {balLoading && <div className="loading-spinner" style={{ margin: '1rem auto' }} />}
        {!balLoading && balData && (
          <>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>کد دانشجویی</th>
                    <th>نام</th>
                    <th style={{ textAlign: 'left' }}>پرداخت‌ها</th>
                    <th style={{ textAlign: 'left' }}>بستانکاری</th>
                    <th style={{ textAlign: 'left' }}>بدهی + جریمه</th>
                    <th style={{ textAlign: 'left' }}>مانده</th>
                  </tr>
                </thead>
                <tbody>
                  {(balData.items || []).map((row) => (
                    <tr key={row.student_id}>
                      <td style={{ direction: 'ltr', textAlign: 'right' }}>{row.student_code}</td>
                      <td>{row.student_name_fa || '—'}</td>
                      <td style={{ textAlign: 'left' }}>{fmtMoney(row.total_payments)}</td>
                      <td style={{ textAlign: 'left' }}>{fmtMoney(row.total_credits)}</td>
                      <td style={{ textAlign: 'left' }}>{fmtMoney(row.total_debts)}</td>
                      <td
                        style={{
                          textAlign: 'left',
                          fontWeight: 600,
                          color: row.balance < 0 ? '#b91c1c' : row.balance > 0 ? '#15803d' : undefined,
                        }}
                      >
                        {fmtMoney(row.balance)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {paginate(balData.page, balData.pages, setBalPage)}
          </>
        )}
      </div>

      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div className="card-header">
          <h3 className="card-title">فهرست تراکنش‌ها</h3>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1rem', marginBottom: '1rem', alignItems: 'flex-end' }}>
          <div className="form-group" style={{ marginBottom: 0, minWidth: '160px' }}>
            <label className="form-label">نوع رکورد</label>
            <select
              className="form-input"
              value={txType}
              onChange={(e) => {
                setTxPage(1)
                setTxType(e.target.value)
              }}
            >
              <option value="">همه</option>
              {Object.entries(TYPE_LABELS).map(([k, lab]) => (
                <option key={k} value={k}>
                  {lab}
                </option>
              ))}
            </select>
          </div>
          <div className="form-group" style={{ marginBottom: 0, flex: '1 1 220px' }}>
            <label className="form-label">جستجو (کد، نام، شرح)</label>
            <input
              className="form-input"
              value={txQ}
              onChange={(e) => {
                setTxPage(1)
                setTxQ(e.target.value)
              }}
              placeholder="مثلاً DEMO یا پرداخت"
              style={{ direction: 'rtl' }}
            />
          </div>
        </div>
        {txLoading && <div className="loading-spinner" style={{ margin: '1rem auto' }} />}
        {!txLoading && txData && (
          <>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>تاریخ</th>
                    <th>کد</th>
                    <th>نام</th>
                    <th>نوع</th>
                    <th style={{ textAlign: 'left' }}>مبلغ</th>
                    <th>شرح</th>
                  </tr>
                </thead>
                <tbody>
                  {(txData.items || []).map((row) => (
                    <tr key={row.id}>
                      <td style={{ fontSize: '0.85rem', whiteSpace: 'nowrap' }}>{fmtDate(row.created_at)}</td>
                      <td style={{ direction: 'ltr', fontSize: '0.85rem' }}>{row.student_code}</td>
                      <td>{row.student_name_fa || '—'}</td>
                      <td>
                        <span className="badge badge-primary badge-tight">{TYPE_LABELS[row.record_type] || row.record_type}</span>
                      </td>
                      <td style={{ textAlign: 'left', fontWeight: 600 }}>{fmtMoney(row.amount)}</td>
                      <td style={{ maxWidth: '280px', fontSize: '0.85rem' }}>{row.description_fa || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {paginate(txData.page, txData.pages, setTxPage)}
            <p style={{ marginTop: '0.75rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              مجموع {txData.total?.toLocaleString('fa-IR')} تراکنش مطابق فیلتر
            </p>
          </>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <h3 className="card-title">خروجی برای حسابداری</h3>
        </div>
        <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          فایل CSV حداکثر ۵۰۰۰ رکورد اخیر برای Excel، هلو، سپیدار یا هر نرم‌افزار حسابداری سازگار با جدول.
        </p>
        <button type="button" className="btn btn-primary" disabled={exporting} onClick={handleExport}>
          {exporting ? 'در حال آماده‌سازی…' : 'دانلود CSV'}
        </button>
      </div>
    </div>
  )
}
