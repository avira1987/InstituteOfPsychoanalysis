import React, { useCallback, useEffect, useRef, useState } from 'react'
import { systemApi } from '../services/api'

const REFRESH_MS = 12000

function fmtBytes(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let v = Number(n)
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i += 1
  }
  return `${v.toFixed(v >= 100 || i === 0 ? 0 : 1)} ${units[i]}`
}

function fmtPct(n) {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return `${Number(n).toFixed(1)}٪`
}

function pctColor(pct) {
  if (pct === null || pct === undefined) return 'var(--text-secondary)'
  if (pct >= 90) return 'var(--danger)'
  if (pct >= 75) return 'var(--warning)'
  return 'var(--success)'
}

function MetricCard({ title, primary, secondary, pct }) {
  return (
    <div className="card" style={{ padding: '1.1rem 1.25rem', display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
      <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>{title}</div>
      <div style={{ fontSize: '1.5rem', fontWeight: 700, color: pctColor(pct) }}>{primary}</div>
      {secondary ? (
        <div style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{secondary}</div>
      ) : null}
      {pct !== null && pct !== undefined ? (
        <div style={{ height: 6, background: 'var(--border)', borderRadius: 4, overflow: 'hidden' }}>
          <div
            style={{
              width: `${Math.max(0, Math.min(100, pct))}%`,
              height: '100%',
              background: pctColor(pct),
              transition: 'width 0.4s ease',
            }}
          />
        </div>
      ) : null}
    </div>
  )
}

export default function SystemResourcesPage() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [updatedAt, setUpdatedAt] = useState(null)
  const timerRef = useRef(null)

  const load = useCallback(async () => {
    try {
      const res = await systemApi.resourceSnapshot()
      setData(res.data)
      setError('')
      setUpdatedAt(new Date())
    } catch (err) {
      setError(err?.response?.data?.detail || 'دریافت اطلاعات منابع ناموفق بود')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    timerRef.current = setInterval(load, REFRESH_MS)
    return () => {
      if (timerRef.current) clearInterval(timerRef.current)
    }
  }, [load])

  const host = data?.host_memory
  const cont = data?.container_memory
  const load1pct = data?.load_average?.one_pct
  const disk = data?.disk_root
  const diskPct =
    disk && disk.total_bytes ? Number(((disk.used_bytes / disk.total_bytes) * 100).toFixed(1)) : null

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">منابع سرور</h1>
          <p className="page-subtitle">
            وضعیت لحظه‌ای CPU، حافظه، دیسک و فرایند API
            {updatedAt ? ` — به‌روزرسانی: ${updatedAt.toLocaleTimeString('fa-IR')}` : ''}
          </p>
        </div>
        <div>
          <button type="button" className="btn btn-outline" onClick={load} disabled={loading}>
            {loading ? 'در حال دریافت…' : 'به‌روزرسانی'}
          </button>
        </div>
      </div>

      {error ? (
        <div className="card" style={{ padding: '1rem 1.25rem', borderRight: '4px solid var(--danger)' }}>
          <p style={{ margin: 0, color: 'var(--danger)' }}>{error}</p>
        </div>
      ) : null}

      {!data && !error ? (
        <div className="card" style={{ padding: '1.25rem' }}>
          <p className="muted" style={{ margin: 0 }}>در حال خواندن وضعیت سرور…</p>
        </div>
      ) : null}

      {data ? (
        <>
          {!data.platform_supported ? (
            <div className="card" style={{ padding: '1rem 1.25rem', marginBottom: '1rem', borderRight: '4px solid var(--warning)' }}>
              <p style={{ margin: 0, fontSize: '0.9rem' }}>
                این میزبان لینوکسی نیست (یا /proc در دسترس نیست). فقط فضای دیسک قابل اندازه‌گیری است.
              </p>
            </div>
          ) : null}

          <div
            style={{
              display: 'grid',
              gap: '1rem',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              marginBottom: '1.5rem',
            }}
          >
            <MetricCard
              title="بار CPU (یک دقیقهٔ اخیر)"
              primary={data.load_average ? data.load_average.one.toFixed(2) : '—'}
              secondary={
                data.load_average
                  ? `${data.cpu_count} هسته — ${fmtPct(load1pct)} استفاده`
                  : 'در دسترس نیست'
              }
              pct={load1pct ?? null}
            />
            <MetricCard
              title="حافظهٔ کانتینر API"
              primary={cont ? fmtBytes(cont.used_bytes) : '—'}
              secondary={
                cont
                  ? `سقف ${fmtBytes(cont.limit_bytes)} — ${fmtPct(cont.used_pct)}`
                  : 'بدون cgroup limit (Docker mem_limit ست نشده)'
              }
              pct={cont?.used_pct ?? null}
            />
            <MetricCard
              title="حافظهٔ کل میزبان"
              primary={host ? fmtBytes(host.used_bytes) : '—'}
              secondary={
                host
                  ? `از ${fmtBytes(host.total_bytes)} — ${fmtPct(host.used_pct)}`
                  : 'در دسترس نیست'
              }
              pct={host?.used_pct ?? null}
            />
            <MetricCard
              title="فرایند API (RSS)"
              primary={fmtBytes(data.api_process_rss_bytes)}
              secondary="حافظهٔ مصرفی پروسهٔ uvicorn (داخل کانتینر)"
              pct={
                cont?.limit_bytes && data.api_process_rss_bytes
                  ? Number(((data.api_process_rss_bytes / cont.limit_bytes) * 100).toFixed(1))
                  : null
              }
            />
            <MetricCard
              title="دیسک ریشه (/)"
              primary={disk ? fmtBytes(disk.used_bytes) : '—'}
              secondary={
                disk
                  ? `از ${fmtBytes(disk.total_bytes)} — آزاد ${fmtBytes(disk.free_bytes)}`
                  : 'در دسترس نیست'
              }
              pct={diskPct}
            />
          </div>

          <div className="card" style={{ padding: '1rem 1.25rem' }}>
            <h3 className="card-title" style={{ marginTop: 0, marginBottom: '0.75rem' }}>توضیح کوتاه</h3>
            <ul style={{ margin: 0, paddingRight: '1.25rem', color: 'var(--text-secondary)', fontSize: '0.9rem', lineHeight: 1.85 }}>
              <li>«بار CPU» میانگین استفادهٔ تمام هسته‌ها در یک/پنج/پانزده دقیقهٔ اخیر است؛ &gt;۹۰٪ یعنی فشار شدید.</li>
              <li>«حافظهٔ کانتینر» سقف ست‌شده در docker-compose را نسبت به مصرف لحظه‌ای نشان می‌دهد. اگر «بدون cgroup limit» نشان داد، در docker-compose.prod.yml مقادیر mem_limit ثبت نشده.</li>
              <li>«RSS» بخش غیراشتراکی حافظهٔ پروسهٔ uvicorn است؛ افزایش بدون توقف یعنی نشت حافظه.</li>
              <li>اعداد هر ۱۲ ثانیه به‌روزرسانی می‌شوند.</li>
            </ul>
          </div>
        </>
      ) : null}
    </div>
  )
}
