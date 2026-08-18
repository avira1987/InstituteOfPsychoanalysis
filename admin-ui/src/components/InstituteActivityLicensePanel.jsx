import React, { useCallback, useEffect, useState } from 'react'
import { semesterPrepApi } from '../services/api'

/**
 * ویرایش شماره پروانه فعالیت انستیتو بدون بازگشت فرایند آماده‌سازی.
 */
export default function InstituteActivityLicensePanel({ showToast, onUpdated }) {
  const [number, setNumber] = useState('')
  const [saved, setSaved] = useState('')
  const [source, setSource] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await semesterPrepApi.getActivityLicense()
      const value = (res.data?.activity_license_number || '').trim()
      setNumber(value)
      setSaved(value)
      setSource(res.data?.source || null)
    } catch {
      showToast?.('خطا در بارگذاری شماره پروانه', 'error')
    } finally {
      setLoading(false)
    }
  }, [showToast])

  useEffect(() => {
    load()
  }, [load])

  const handleSave = async (e) => {
    e.preventDefault()
    const next = number.trim()
    if (!next) {
      showToast?.('شماره پروانه را وارد کنید.', 'error')
      return
    }
    setSaving(true)
    try {
      const res = await semesterPrepApi.patchActivityLicense({ activity_license_number: next })
      const value = (res.data?.activity_license_number || next).trim()
      setNumber(value)
      setSaved(value)
      setSource(res.data?.source || 'manual')
      showToast?.('شماره پروانه فعالیت ذخیره شد.')
      onUpdated?.()
    } catch (err) {
      const d = err?.response?.data?.detail
      showToast?.(typeof d === 'string' ? d : 'خطا در ذخیرهٔ شماره پروانه', 'error')
    } finally {
      setSaving(false)
    }
  }

  const dirty = number.trim() !== saved.trim()
  const sourceLabel = source === 'prep' ? 'از فرایند آماده‌سازی' : source === 'manual' ? 'ویرایش دستی' : null

  return (
    <section id="license" data-testid="institute-activity-license-panel">
      <h3 style={{ fontSize: '1.05rem', margin: '0 0 0.35rem' }}>شماره پروانه فعالیت انستیتو</h3>
      <p className="muted" style={{ margin: '0 0 1rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
        این شماره در فرم ثبت‌نام دانشجو نمایش داده می‌شود. می‌توانید آن را اینجا ویرایش کنید
        بدون اینکه به مرحلهٔ «بررسی پروانه» در فرایند آماده‌سازی برگردید.
      </p>

      {loading ? (
        <p className="muted" style={{ fontSize: '0.85rem' }}>در حال بارگذاری…</p>
      ) : (
        <form
          onSubmit={handleSave}
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '0.65rem',
            alignItems: 'flex-end',
          }}
        >
          <label style={{ fontSize: '0.85rem', flex: '1 1 220px' }}>
            شماره پروانه فعالیت
            <input
              type="text"
              value={number}
              onChange={(e) => setNumber(e.target.value)}
              placeholder="مثلاً ۱۲۳۴۵۶"
              style={{ display: 'block', width: '100%', marginTop: '0.25rem', direction: 'ltr', textAlign: 'right' }}
              data-testid="activity-license-input"
            />
          </label>
          <button
            type="submit"
            className="btn btn-primary btn-sm"
            disabled={saving || !dirty}
            data-testid="activity-license-save"
          >
            {saving ? 'در حال ذخیره…' : 'ذخیره'}
          </button>
          {saved ? (
            <span className="muted" style={{ fontSize: '0.8rem' }}>
              فعلی: <strong style={{ direction: 'ltr', display: 'inline-block' }}>{saved}</strong>
              {sourceLabel ? ` (${sourceLabel})` : ''}
            </span>
          ) : (
            <span className="muted" style={{ fontSize: '0.8rem' }}>هنوز شماره‌ای ثبت نشده است.</span>
          )}
        </form>
      )}
    </section>
  )
}
