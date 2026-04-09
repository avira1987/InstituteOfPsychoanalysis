import React, { useState, useEffect, useCallback } from 'react'
import { reportsApi } from '../services/api'

const REPORTS = [
  { key: 1, label: '۱ — گزارش ماهانه تخلف', desc: 'پرونده‌های ثبت تخلف، تجمیع ماه و سال' },
  { key: 2, label: '۲ — گزارش ماهانه بدهکاری', desc: 'مانده بدهکاران و ریز نوبت‌های بدهی در ماه' },
  { key: 3, label: '۳ — گزارش ریزش و انصراف', desc: 'ثبت‌نام جامع گیرکرده پس از پذیرش؛ مرخصی در ماه' },
  { key: 4, label: '۴ — گزارش تأخیر (نقض مهلت)', desc: 'رویدادهای نقض مهلت فرایند در ماه' },
  { key: 5, label: '۵ — گزارش کنسلی و غیبت', desc: 'جلسات لغوشده و غیبت ثبت‌شده در ماه' },
]

export default function ReportsHubPage() {
  const [year, setYear] = useState(1403)
  const [month, setMonth] = useState(1)
  const [exportFormat, setExportFormat] = useState('pdf')
  /** رکوردهای بارگذاری‌شده برای آموزش/تست — پیش‌فرض در گزارش لحاظ نمی‌شوند */
  const [includeSampleData, setIncludeSampleData] = useState(false)
  const [loadingKey, setLoadingKey] = useState(null)
  const [error, setError] = useState(null)

  const loadShamsiDefaults = useCallback(async () => {
    try {
      const res = await reportsApi.shamsiToday()
      const y = res.data?.year
      const m = res.data?.month
      if (y) setYear(y)
      if (m) setMonth(m)
    } catch (_) {
      /* بدون توکن یا خطا — مقدار پیش‌فرض دستی */
    }
  }, [])

  useEffect(() => {
    loadShamsiDefaults()
  }, [loadShamsiDefaults])

  const onDownload = async (reportKey) => {
    setError(null)
    setLoadingKey(reportKey)
    try {
      await reportsApi.downloadMonthly(reportKey, year, month, exportFormat, includeSampleData)
    } catch (e) {
      const msg = e?.message || 'خطا در دریافت گزارش'
      setError(typeof msg === 'string' ? msg : 'خطا در دریافت گزارش')
    } finally {
      setLoadingKey(null)
    }
  }

  return (
    <div className="reports-page" dir="rtl" lang="fa">
      <div className="page-header">
        <div>
          <h1 className="page-title">گزارشات</h1>
          <p className="page-subtitle">
            سال و ماه شمسی را انتخاب کنید؛ گزارش را به‌صورت PDF، اکسل یا CSV دریافت کنید. خروجی‌ها برای خوانایی فارسی راست‌چین
            و مناسب بایگانی تنظیم شده‌اند.
          </p>
        </div>
      </div>

      {error && (
        <div className="toast toast-error" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      <div className="card" style={{ marginBottom: '1.25rem' }}>
        <div className="card-header">
          <h2 className="card-title">بازهٔ ماهانه</h2>
        </div>
        <div className="reports-filters-row">
          <label className="input-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>سال</span>
            <input
              type="number"
              className="input"
              min={1300}
              max={1500}
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
            />
          </label>
          <label className="input-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>ماه (۱–۱۲)</span>
            <input
              type="number"
              className="input"
              min={1}
              max={12}
              value={month}
              onChange={(e) => setMonth(Number(e.target.value))}
            />
          </label>
          <label className="input-group" style={{ display: 'flex', flexDirection: 'column', gap: '0.35rem' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>فرمت فایل</span>
            <select
              className="input"
              value={exportFormat}
              onChange={(e) => setExportFormat(e.target.value)}
              style={{ minWidth: '10rem' }}
            >
              <option value="xlsx">Excel (.xlsx)</option>
              <option value="csv">CSV (جداکننده ؛)</option>
              <option value="pdf">PDF</option>
            </select>
          </label>
          <label
            className="input-group"
            style={{
              display: 'flex',
              flexDirection: 'row',
              alignItems: 'center',
              gap: '0.5rem',
              alignSelf: 'flex-end',
              cursor: 'pointer',
            }}
          >
            <input
              type="checkbox"
              checked={includeSampleData}
              onChange={(e) => setIncludeSampleData(e.target.checked)}
            />
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>شامل رکوردهای نمونه آموزشی</span>
          </label>
        </div>
      </div>

      <div className="reports-download-grid">
        {REPORTS.map((r) => (
          <div key={r.key} className="card reports-download-card">
            <div className="reports-download-card-body">
              <h3 className="reports-download-title">{r.label}</h3>
              <p className="reports-download-desc">{r.desc}</p>
            </div>
            <button
              type="button"
              className="btn btn-primary"
              disabled={loadingKey != null}
              onClick={() => onDownload(r.key)}
            >
              {loadingKey === r.key ? 'در حال تولید…' : 'دانلود'}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
