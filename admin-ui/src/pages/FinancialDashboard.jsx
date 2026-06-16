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

/** بخش جمع‌شونده؛ یا کارت ثابت (collapsible=false) برای تنظیماتی که باید همیشه دیده شوند */
function FinancePanel({ title, children, defaultOpen = false, collapsible = true }) {
  if (!collapsible) {
    return (
      <section className="card finance-panel finance-panel--static">
        <h3 className="finance-panel__summary-title card-title" style={{ marginBottom: '1rem' }}>
          {title}
        </h3>
        <div className="finance-panel__body">{children}</div>
      </section>
    )
  }
  return (
    <details className="card finance-panel" defaultOpen={defaultOpen}>
      <summary>
        <h3 className="finance-panel__summary-title card-title">{title}</h3>
        <span className="finance-panel__chevron" aria-hidden>
          ▼
        </span>
      </summary>
      <div className="finance-panel__body">{children}</div>
    </details>
  )
}

/** پیش‌فرض زمانی که API هنوز جواب نداده یا خطا باشد — هم‌سو با app/config */
const FALLBACK_PROGRAM_FINANCIAL = {
  registration_interview_fee_rial: '5000000',
  registration_tuition_invoice_toman: '120000000',
  start_therapy_first_session_fee_rial: '10000000',
  extra_session_fee_rial: '7500000',
  default_therapy_session_fee_toman: '500000',
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

  const [gapDays, setGapDays] = useState('25')
  const [countOptsStr, setCountOptsStr] = useState('2, 3, 4')
  const [instSaving, setInstSaving] = useState(false)
  const [instLoaded, setInstLoaded] = useState(false)
  const [instUpdatedAt, setInstUpdatedAt] = useState(null)

  const [progLoaded, setProgLoaded] = useState(false)
  const [progSaving, setProgSaving] = useState(false)
  const [progUpdatedAt, setProgUpdatedAt] = useState(null)
  const [interviewRial, setInterviewRial] = useState('')
  const [tuitionToman, setTuitionToman] = useState('')
  const [therapyFirstRial, setTherapyFirstRial] = useState('')
  const [extraRial, setExtraRial] = useState('')
  const [therapySessionToman, setTherapySessionToman] = useState('')
  const [classSessionToman, setClassSessionToman] = useState('')
  const [courseSessionToman, setCourseSessionToman] = useState('')
  const [extraSessionTomanHint, setExtraSessionTomanHint] = useState(null)
  const [progSourcesNote, setProgSourcesNote] = useState('')

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
    financeApi
      .installmentSettings()
      .then((r) => {
        const d = r.data || {}
        setGapDays(String(d.term2_installment_gap_days ?? 25))
        setCountOptsStr((d.installment_count_options || [2, 3, 4]).join(', '))
        setInstUpdatedAt(d.updated_at || null)
        setInstLoaded(true)
      })
      .catch(() => {
        setInstLoaded(true)
      })
  }, [])

  useEffect(() => {
    financeApi
      .programFinancialDefaults()
      .then((r) => {
        const d = r.data || {}
        setInterviewRial(String(d.registration_interview_fee_rial ?? ''))
        setTuitionToman(String(d.registration_tuition_invoice_toman ?? ''))
        setTherapyFirstRial(String(d.start_therapy_first_session_fee_rial ?? ''))
        setExtraRial(String(d.extra_session_fee_rial ?? ''))
        setTherapySessionToman(String(d.default_therapy_session_fee_toman ?? ''))
        setClassSessionToman(
          d.class_session_fee_toman != null && Number(d.class_session_fee_toman) > 0
            ? String(d.class_session_fee_toman)
            : '',
        )
        setCourseSessionToman(
          d.course_session_fee_toman != null && Number(d.course_session_fee_toman) > 0
            ? String(d.course_session_fee_toman)
            : '',
        )
        setExtraSessionTomanHint(d.extra_session_fee_toman != null ? d.extra_session_fee_toman : null)
        setProgUpdatedAt(d.updated_at || null)
        setProgSourcesNote(typeof d.sources_note === 'string' ? d.sources_note : '')
        setProgLoaded(true)
      })
      .catch(() => {
        setInterviewRial(FALLBACK_PROGRAM_FINANCIAL.registration_interview_fee_rial)
        setTuitionToman(FALLBACK_PROGRAM_FINANCIAL.registration_tuition_invoice_toman)
        setTherapyFirstRial(FALLBACK_PROGRAM_FINANCIAL.start_therapy_first_session_fee_rial)
        setExtraRial(FALLBACK_PROGRAM_FINANCIAL.extra_session_fee_rial)
        setTherapySessionToman(FALLBACK_PROGRAM_FINANCIAL.default_therapy_session_fee_toman)
        setClassSessionToman('')
        setCourseSessionToman('')
        setExtraSessionTomanHint(
          Number(FALLBACK_PROGRAM_FINANCIAL.extra_session_fee_rial) / 10,
        )
        setProgSourcesNote('')
        setProgLoaded(true)
      })
  }, [])

  const saveProgramFinancialDefaults = async () => {
    setErr(null)
    setProgSaving(true)
    try {
      const parseIntSafe = (v) => {
        const n = parseInt(String(v).replace(/[,\s،]/g, ''), 10)
        return Number.isNaN(n) ? null : n
      }
      const parseFloatSafe = (v) => {
        const s = String(v).replace(/[,\s،]/g, '').replace(/[^\d.-]/g, '')
        const n = parseFloat(s)
        return Number.isNaN(n) ? null : n
      }
      const ri1 = parseIntSafe(interviewRial)
      const tuition = parseFloatSafe(tuitionToman)
      const st = parseIntSafe(therapyFirstRial)
      const ex = parseIntSafe(extraRial)
      const th = parseFloatSafe(therapySessionToman)
      if (ri1 == null || ri1 < 1000) {
        setErr('هزینهٔ مصاحبه (ریال) باید حداقل ۱۰۰۰ باشد.')
        return
      }
      if (tuition == null || tuition <= 0) {
        setErr('مبلغ شهریه/فاکتور ثبت‌نام (تومان) را به‌درستی وارد کنید.')
        return
      }
      if (st == null || st < 1000) {
        setErr('مبلغ اولین جلسه درمان (ریال) باید حداقل ۱۰۰۰ باشد.')
        return
      }
      if (ex == null || ex < 1000) {
        setErr('مبلغ جلسه اضافه (ریال) باید حداقل ۱۰۰۰ باشد.')
        return
      }
      if (th == null || th <= 0) {
        setErr('پیش‌فرض هر جلسه درمان آموزشی (تومان) باید بزرگ‌تر از صفر باشد.')
        return
      }
      const cl = String(classSessionToman).trim() === '' ? 0 : parseFloatSafe(classSessionToman)
      const cr = String(courseSessionToman).trim() === '' ? 0 : parseFloatSafe(courseSessionToman)
      if (cl == null || cl < 0) {
        setErr('«پیش‌فرض هر جلسه کلاس» باید خالی یا عدد نامنفی باشد.')
        return
      }
      if (cr == null || cr < 0) {
        setErr('«پیش‌فرض هر جلسه دوره» باید خالی یا عدد نامنفی باشد.')
        return
      }
      const r = await financeApi.patchProgramFinancialDefaults({
        registration_interview_fee_rial: ri1,
        registration_tuition_invoice_toman: tuition,
        start_therapy_first_session_fee_rial: st,
        extra_session_fee_rial: ex,
        default_therapy_session_fee_toman: th,
        class_session_fee_toman: cl,
        course_session_fee_toman: cr,
      })
      const d = r.data || {}
      setInterviewRial(String(d.registration_interview_fee_rial ?? ''))
      setTuitionToman(String(d.registration_tuition_invoice_toman ?? ''))
      setTherapyFirstRial(String(d.start_therapy_first_session_fee_rial ?? ''))
      setExtraRial(String(d.extra_session_fee_rial ?? ''))
      setTherapySessionToman(String(d.default_therapy_session_fee_toman ?? ''))
      setClassSessionToman(
        d.class_session_fee_toman != null && Number(d.class_session_fee_toman) > 0
          ? String(d.class_session_fee_toman)
          : '',
      )
      setCourseSessionToman(
        d.course_session_fee_toman != null && Number(d.course_session_fee_toman) > 0
          ? String(d.course_session_fee_toman)
          : '',
      )
      setExtraSessionTomanHint(d.extra_session_fee_toman != null ? d.extra_session_fee_toman : null)
      setProgUpdatedAt(d.updated_at || null)
      setProgSourcesNote(typeof d.sources_note === 'string' ? d.sources_note : '')
    } catch (e) {
      setErr(e.response?.data?.detail || e.message)
    } finally {
      setProgSaving(false)
    }
  }

  const saveInstallmentSettings = async () => {
    setErr(null)
    setInstSaving(true)
    try {
      const parts = countOptsStr.split(/[,،\s]+/).map((s) => s.trim()).filter(Boolean)
      const installment_count_options = parts
        .map((s) => parseInt(s, 10))
        .filter((n) => !Number.isNaN(n) && n >= 2 && n <= 24)
      const g = parseInt(String(gapDays).replace(/[^\d]/g, ''), 10)
      if (Number.isNaN(g) || g < 1 || g > 365) {
        setErr('فاصلهٔ روزهای بین اقساط باید بین ۱ تا ۳۶۵ باشد.')
        return
      }
      if (installment_count_options.length === 0) {
        setErr('حداقل یک گزینه برای تعداد اقساط وارد کنید (مثلاً ۲، ۳، ۴).')
        return
      }
      const r = await financeApi.patchInstallmentSettings({
        term2_installment_gap_days: g,
        installment_count_options,
      })
      const d = r.data || {}
      setGapDays(String(d.term2_installment_gap_days ?? g))
      setCountOptsStr((d.installment_count_options || installment_count_options).join(', '))
      setInstUpdatedAt(d.updated_at || null)
    } catch (e) {
      setErr(e.response?.data?.detail || e.message)
    } finally {
      setInstSaving(false)
    }
  }

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
            بررسی تراکنش‌ها، بدهی و بستانکاری، مانده دانشجویان و هم‌ترازی با حسابداری مراکز آموزشی؛ ویرایش{' '}
            <strong>مبالغ پیش‌فرض ثبت‌نام، جلسات درمان/کلاس/دوره</strong> و <strong>تنظیمات اقساط</strong> در پنل‌های
            بازشوندهٔ ابتدای همین صفحه — دسترسی فقط برای نقش اپراتور مالی (مدیر سیستم به‌صورت سرپرست)
          </p>
        </div>
      </div>

      {err && (
        <div className="card" style={{ borderColor: '#fca5a5', background: '#fef2f2', marginBottom: '1rem' }}>
          {err}
        </div>
      )}

      {instLoaded && (
        <FinancePanel title="تنظیمات اقساط وب‌سایت" collapsible={false}>
          <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.7 }}>
            فاصلهٔ روز بین سررسید هر قسط (ترم دوم آشنایی و فرایندهایی که از «ادغام زمینهٔ اقساط» استفاده می‌کنند) و گزینه‌های
            مجاز تعداد اقساط برای نمایش در بخش عمومی (
            <code style={{ fontSize: '0.85rem' }}>/api/public/installment-policy</code>
            ). فرم‌های ثبت‌نام در متادیتا ممکن است جداگانه به‌روز شوند.
          </p>
          <div
            style={{
              display: 'grid',
              gap: '1rem',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              alignItems: 'flex-end',
            }}
          >
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">فاصلهٔ سررسید اقساط (روز)</label>
              <input
                className="form-input"
                type="text"
                inputMode="numeric"
                value={gapDays}
                onChange={(e) => setGapDays(e.target.value)}
                placeholder="مثلاً ۲۵"
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0, gridColumn: 'span 1' }}>
              <label className="form-label">گزینه‌های تعداد اقساط (با ویرگول جدا کنید)</label>
              <input
                className="form-input"
                type="text"
                value={countOptsStr}
                onChange={(e) => setCountOptsStr(e.target.value)}
                placeholder="۲، ۳، ۴"
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center' }}>
              <button type="button" className="btn btn-primary" disabled={instSaving} onClick={saveInstallmentSettings}>
                {instSaving ? 'در حال ذخیره…' : 'ذخیرهٔ تنظیمات'}
              </button>
              {instUpdatedAt && (
                <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                  آخرین به‌روزرسانی: {fmtDate(instUpdatedAt)}
                </span>
              )}
            </div>
          </div>
        </FinancePanel>
      )}

      {progLoaded && (
        <FinancePanel title="تنظیمات مالی: ثبت‌نام، جلسات درمان، کلاس و دورهٔ جلسه‌ای" collapsible={false}>
          {progSourcesNote ? (
            <p style={{ marginBottom: '1rem', fontSize: '0.82rem', color: 'var(--text-muted, #64748b)', lineHeight: 1.65 }}>
              {progSourcesNote}
            </p>
          ) : null}
          <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.75 }}>
            این مقادیر برای <strong>پرداخت پیش‌فرض ثبت‌نام</strong> (مصاحبه و شهریه)، <strong>آغاز درمان آموزشی</strong>{' '}
            و <strong>جلسه اضافه درمان</strong> استفاده می‌شوند. مبالغ پیش‌فرض هر جلسهٔ{' '}
            <strong>کلاس</strong> و <strong>دورهٔ جلسه‌ای</strong> در زمینهٔ پرداخت جلسات درمان به‌صورت مرجع (راهنما) به
            پنل دانشجو اضافه می‌شود؛ مبلغ واقعی هر فرایند ممکن است در همان فرایند ست شود.
            {extraSessionTomanHint != null && (
              <span>
                {' '}
                معادل تومانی جلسه اضافه از روی ریال:{' '}
                <strong>{fmtMoney(extraSessionTomanHint)}</strong> تومان.
              </span>
            )}
          </p>
          <p style={{ marginBottom: '1rem', fontSize: '0.85rem', color: 'var(--text-muted, #64748b)' }}>
            درگاه پرداخت مبلغ را به ریال می‌گیرد؛ فاکتور داخلی شهریه به تومان است.
          </p>
          <div
            style={{
              display: 'grid',
              gap: '1rem',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              alignItems: 'flex-end',
            }}
          >
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">هزینه مصاحبه ثبت‌نام (ریال)</label>
              <input
                className="form-input"
                type="text"
                inputMode="numeric"
                value={interviewRial}
                onChange={(e) => setInterviewRial(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">شهریه / فاکتور ثبت‌نام (تومان)</label>
              <input
                className="form-input"
                type="text"
                inputMode="decimal"
                value={tuitionToman}
                onChange={(e) => setTuitionToman(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">اولین جلسه درمان آموزشی (ریال)</label>
              <input
                className="form-input"
                type="text"
                inputMode="numeric"
                value={therapyFirstRial}
                onChange={(e) => setTherapyFirstRial(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">جلسه اضافه درمان (ریال)</label>
              <input
                className="form-input"
                type="text"
                inputMode="numeric"
                value={extraRial}
                onChange={(e) => setExtraRial(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">پیش‌فرض هر جلسه درمان آموزشی (تومان)</label>
              <input
                className="form-input"
                type="text"
                inputMode="decimal"
                value={therapySessionToman}
                onChange={(e) => setTherapySessionToman(e.target.value)}
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">پیش‌فرض هر جلسه کلاس آموزشی (تومان، اختیاری)</label>
              <input
                className="form-input"
                type="text"
                inputMode="decimal"
                value={classSessionToman}
                onChange={(e) => setClassSessionToman(e.target.value)}
                placeholder="خالی = بدون مرجع مبلغ"
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
            <div className="form-group" style={{ marginBottom: 0 }}>
              <label className="form-label">پیش‌فرض هر جلسه دوره جلسه‌ای (تومان، اختیاری)</label>
              <input
                className="form-input"
                type="text"
                inputMode="decimal"
                value={courseSessionToman}
                onChange={(e) => setCourseSessionToman(e.target.value)}
                placeholder="خالی = بدون مرجع مبلغ"
                style={{ direction: 'ltr', textAlign: 'right' }}
              />
            </div>
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'center', marginTop: '1rem' }}>
            <button type="button" className="btn btn-primary" disabled={progSaving} onClick={saveProgramFinancialDefaults}>
              {progSaving ? 'در حال ذخیره…' : 'ذخیرهٔ تنظیمات مالی برنامه'}
            </button>
            {progUpdatedAt && (
              <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                آخرین به‌روزرسانی: {fmtDate(progUpdatedAt)}
              </span>
            )}
          </div>
        </FinancePanel>
      )}

      <FinancePanel title="خلاصهٔ آمار">
        <div className="stats-grid">
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
      </FinancePanel>

      {ctx && (
        <FinancePanel title={ctx.title}>
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
        </FinancePanel>
      )}

      {summary && (
        <FinancePanel title="معادلات و شاخص‌های مالی">
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
        </FinancePanel>
      )}

      {summary && breakdownRows.length > 0 && (
        <FinancePanel title="تفکیک بر اساس نوع رکورد">
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
        </FinancePanel>
      )}

      <FinancePanel title="مانده مالی دانشجویان (بدهی / بستانکاری)">
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
      </FinancePanel>

      <FinancePanel title="فهرست تراکنش‌ها">
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
      </FinancePanel>

      <FinancePanel title="خروجی برای حسابداری">
        <p style={{ marginBottom: '1rem', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          فایل CSV حداکثر ۵۰۰۰ رکورد اخیر برای Excel، هلو، سپیدار یا هر نرم‌افزار حسابداری سازگار با جدول.
        </p>
        <button type="button" className="btn btn-primary" disabled={exporting} onClick={handleExport}>
          {exporting ? 'در حال آماده‌سازی…' : 'دانلود CSV'}
        </button>
      </FinancePanel>
    </div>
  )
}
