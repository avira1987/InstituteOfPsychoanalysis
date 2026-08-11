import React, { useCallback, useEffect, useState } from 'react'
import { systemApi } from '../services/api'

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

function statusLabel(status) {
  if (status === 'ok') return 'سالم'
  if (status === 'incomplete') return 'ناقص'
  return status || '—'
}

function triggerBlobDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}

export default function BackupSnapshotsPage() {
  const [items, setItems] = useState([])
  const [backupDir, setBackupDir] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [busyKey, setBusyKey] = useState('')
  const [verifyMsg, setVerifyMsg] = useState({})

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await systemApi.listBackups()
      setItems(Array.isArray(res.data?.items) ? res.data.items : [])
      setBackupDir(res.data?.backup_dir || '')
      setError('')
    } catch (err) {
      setError(err?.response?.data?.detail || 'دریافت فهرست بکاپ‌ها ناموفق بود')
      setItems([])
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const onVerify = async (date) => {
    const key = `v:${date}`
    setBusyKey(key)
    setVerifyMsg((m) => ({ ...m, [date]: '' }))
    try {
      const res = await systemApi.getBackup(date, { verify: true })
      const ok = res.data?.verified
      setVerifyMsg((m) => ({
        ...m,
        [date]: ok ? 'اعتبارسنجی موفق بود' : 'عدم تطابق چک‌سام یا فایل ناقص',
      }))
    } catch (err) {
      setVerifyMsg((m) => ({
        ...m,
        [date]: err?.response?.data?.detail || 'اعتبارسنجی ناموفق',
      }))
    } finally {
      setBusyKey('')
    }
  }

  const onDownload = async (date, kind) => {
    const key = `d:${date}:${kind}`
    setBusyKey(key)
    try {
      const res = await systemApi.downloadBackup(date, kind)
      const name = kind === 'db' ? `anistito-${date}-db.dump` : `anistito-${date}-uploads.tar.gz`
      triggerBlobDownload(res.data, name)
    } catch (err) {
      setError(err?.response?.data?.detail || `دانلود ${kind} ناموفق بود`)
    } finally {
      setBusyKey('')
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">بکاپ‌ها / اسنپ‌شات‌ها</h1>
          <p className="page-subtitle">
            فهرست بکاپ‌های روزانه روی هاست
            {backupDir ? ` (${backupDir})` : ''}
            {' — '}
            بازگردانی خودکار روی سایت زنده از این صفحه انجام نمی‌شود
          </p>
        </div>
        <div>
          <button type="button" className="btn btn-outline" onClick={load} disabled={loading}>
            {loading ? 'در حال دریافت…' : 'به‌روزرسانی'}
          </button>
        </div>
      </div>

      <div
        className="card"
        style={{
          padding: '0.9rem 1.1rem',
          marginBottom: '1rem',
          borderRight: '4px solid var(--warning)',
        }}
      >
        <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
          برای بازیابی یک تاریخ خاص روی محیط تست از اسکریپت
          {' '}
          <code>scripts/restore_snapshot.sh</code>
          {' '}
          و راهنمای
          {' '}
          <code>docs/BACKUP_RESTORE_RUNBOOK_FA.md</code>
          {' '}
          استفاده کنید.
        </p>
      </div>

      {error ? (
        <div className="card" style={{ padding: '1rem 1.25rem', borderRight: '4px solid var(--danger)' }}>
          <p style={{ margin: 0, color: 'var(--danger)' }}>{error}</p>
        </div>
      ) : null}

      <div className="card" style={{ padding: 0, overflow: 'auto' }}>
        <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr>
              <th style={{ textAlign: 'right', padding: '0.75rem 1rem' }}>تاریخ</th>
              <th style={{ textAlign: 'right', padding: '0.75rem 1rem' }}>زمان ثبت</th>
              <th style={{ textAlign: 'right', padding: '0.75rem 1rem' }}>وضعیت</th>
              <th style={{ textAlign: 'right', padding: '0.75rem 1rem' }}>حجم</th>
              <th style={{ textAlign: 'right', padding: '0.75rem 1rem' }}>عملیات</th>
            </tr>
          </thead>
          <tbody>
            {!loading && items.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ padding: '1.25rem', color: 'var(--text-secondary)' }}>
                  هنوز بکاپ تاریخ‌داری در مسیر پیکربندی‌شده یافت نشد.
                </td>
              </tr>
            ) : null}
            {items.map((row) => (
              <tr key={row.date} style={{ borderTop: '1px solid var(--border)' }}>
                <td style={{ padding: '0.75rem 1rem', fontWeight: 600 }}>{row.date}</td>
                <td style={{ padding: '0.75rem 1rem', fontSize: '0.85rem' }}>
                  {row.taken_at || '—'}
                </td>
                <td style={{ padding: '0.75rem 1rem' }}>{statusLabel(row.status)}</td>
                <td style={{ padding: '0.75rem 1rem' }}>{fmtBytes(row.total_size_bytes)}</td>
                <td style={{ padding: '0.75rem 1rem' }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem', alignItems: 'center' }}>
                    <button
                      type="button"
                      className="btn btn-outline"
                      style={{ fontSize: '0.8rem' }}
                      disabled={busyKey === `v:${row.date}`}
                      onClick={() => onVerify(row.date)}
                    >
                      {busyKey === `v:${row.date}` ? '…' : 'اعتبارسنجی'}
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline"
                      style={{ fontSize: '0.8rem' }}
                      disabled={busyKey === `d:${row.date}:db` || !row.files?.['db.dump']?.present}
                      onClick={() => onDownload(row.date, 'db')}
                    >
                      دانلود DB
                    </button>
                    <button
                      type="button"
                      className="btn btn-outline"
                      style={{ fontSize: '0.8rem' }}
                      disabled={
                        busyKey === `d:${row.date}:uploads` || !row.files?.['uploads.tar.gz']?.present
                      }
                      onClick={() => onDownload(row.date, 'uploads')}
                    >
                      دانلود فایل‌ها
                    </button>
                  </div>
                  {verifyMsg[row.date] ? (
                    <div
                      style={{
                        marginTop: '0.35rem',
                        fontSize: '0.8rem',
                        color: verifyMsg[row.date].includes('موفق')
                          ? 'var(--success)'
                          : 'var(--danger)',
                      }}
                    >
                      {verifyMsg[row.date]}
                    </div>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
