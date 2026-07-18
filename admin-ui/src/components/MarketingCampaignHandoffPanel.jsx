import React, { useCallback, useMemo, useState } from 'react'
import { processExecApi } from '../services/api'

const HANDOFF_FIELD_NAMES = new Set(['marketing_info_sent_to_manager', 'marketing_notes'])

const ADVANCE_HINT =
  'پس از دانلود PDF: تیک «ارسال شد» را بزنید، «ثبت فرم این مرحله» را بزنید، سپس دکمهٔ پیشروی را بزنید.'

export function isMarketingHandoffField(name) {
  return HANDOFF_FIELD_NAMES.has(name)
}

function buildShareText(processCode) {
  const isWinter = processCode === 'winter_semester_preparation'
  const activities = isWinter ? '۲ و ۳' : '۱، ۲ و ۵'
  const term = isWinter ? 'زمستان' : 'پاییز'
  return (
    `سلام،\n` +
    `بستهٔ اطلاعات شروع کمپین بازاریابی ترم ${term} (خروجی فعالیت‌های ${activities}) را از پورتال انستیتو دریافت و پیوست می‌کنم.\n` +
    `لطفاً برای شروع تبلیغات پذیرش ${term} اقدام فرمایید.`
  )
}

async function parseApiErrorDetail(error) {
  const status = error?.response?.status
  const d = error?.response?.data
  let msg = error?.message || 'خطا در دریافت PDF'

  if (d instanceof Blob) {
    try {
      const txt = await d.text()
      const parsed = JSON.parse(txt)
      if (parsed?.detail) {
        msg = typeof parsed.detail === 'string' ? parsed.detail : msg
      }
    } catch {
      /* ignore */
    }
  } else if (typeof d?.detail === 'string') {
    msg = d.detail
  }

  if (status === 401) {
    return 'نشست ورود منقضی شده — دوباره وارد شوید.'
  }
  if (status === 403) {
    return msg.includes('Only operators')
      ? 'فقط اپراتورها می‌توانند PDF بگیرند.'
      : msg || 'شما مجوز دانلود PDF این مرحله را ندارید.'
  }
  if (status === 400) {
    return msg || 'دانلود PDF فقط در مرحلهٔ کمپین بازاریابی ممکن است.'
  }
  if (status === 503) {
    return msg || 'فونت PDF روی سرور موجود نیست — با پشتیبانی تماس بگیرید.'
  }
  if (status === 500) {
    return msg || 'تولید PDF با خطا مواجه شد.'
  }
  return msg
}

function fieldMeta(form, name) {
  for (const f of form?.fields || []) {
    if (f?.name === name) return f
  }
  return null
}

export default function MarketingCampaignHandoffPanel({
  instanceId,
  processCode,
  showToast,
  form,
  values = {},
  onChange,
  disabled = false,
  readOnly = false,
}) {
  const [busy, setBusy] = useState(false)

  const shareText = useMemo(() => buildShareText(processCode), [processCode])
  const isWinter = processCode === 'winter_semester_preparation'
  const activitiesLabel = isWinter ? '۲ و ۳' : '۱، ۲ و ۵'

  const sentMeta = fieldMeta(form, 'marketing_info_sent_to_manager')
  const notesMeta = fieldMeta(form, 'marketing_notes')
  const sentLabel =
    sentMeta?.label_fa ||
    'اطلاعات لازم برای شروع کمپین تبلیغاتی برای مدیر مارکتینگ ارسال شد'
  const notesLabel = notesMeta?.label_fa || 'یادداشت انتقال به مدیر مارکتینگ (اختیاری)'
  const sentRequired = sentMeta?.required !== false

  const sentChecked = !!values.marketing_info_sent_to_manager
  const notesValue = values.marketing_notes ?? ''

  const patchValues = useCallback(
    (patch) => {
      if (typeof onChange === 'function') {
        onChange({ ...values, ...patch })
      }
    },
    [onChange, values],
  )

  const downloadPdf = useCallback(async () => {
    if (!instanceId) return
    setBusy(true)
    try {
      await processExecApi.downloadMarketingCampaignPack(instanceId)
      showToast?.(`فایل PDF دانلود شد — برای مدیر مارکتینگ ارسال کنید (واتساپ، بل یا ایمیل). ${ADVANCE_HINT}`)
    } catch (e) {
      const msg = await parseApiErrorDetail(e)
      showToast?.(`${msg} ${ADVANCE_HINT}`, 'error')
    } finally {
      setBusy(false)
    }
  }, [instanceId, showToast])

  const openWhatsApp = useCallback(() => {
    const url = `https://api.whatsapp.com/send?text=${encodeURIComponent(shareText)}`
    window.open(url, '_blank', 'noopener,noreferrer')
  }, [shareText])

  const openEmail = useCallback(() => {
    const subject = isWinter
      ? 'بسته اطلاعات کمپین بازاریابی زمستان'
      : 'بسته اطلاعات کمپین بازاریابی پذیرش'
    const url = `mailto:?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(shareText)}`
    window.location.href = url
  }, [isWinter, shareText])

  const openBale = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(shareText)
      showToast?.('متن پیام کپی شد — در بل پیام بدهید و PDF را پیوست کنید')
    } catch {
      showToast?.('متن را دستی کپی کرده و در بل ارسال کنید', 'error')
    }
    window.open('https://web.bale.ai/', '_blank', 'noopener,noreferrer')
  }, [shareText, showToast])

  const isLocked = disabled || readOnly

  return (
    <div
      data-testid="marketing-campaign-handoff-panel"
      style={{
        marginBottom: '1rem',
        padding: '0.85rem 1rem',
        background: isLocked ? '#f8fafc' : '#fffbeb',
        borderRadius: '8px',
        border: isLocked ? '1px solid #cbd5e1' : '1px solid #fcd34d',
        width: '100%',
        maxWidth: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
        opacity: isLocked ? 0.72 : 1,
        pointerEvents: isLocked ? 'none' : 'auto',
      }}
    >
      <div style={{ fontWeight: 700, fontSize: '0.88rem', marginBottom: '0.35rem', color: '#92400e' }}>
        انتقال اطلاعات به مدیر مارکتینگ
      </div>
      {form?.note_fa ? (
        <p style={{ margin: '0 0 0.5rem', fontSize: '0.82rem', lineHeight: 1.65, color: '#78350f' }}>
          {form.note_fa}
        </p>
      ) : null}
      <ol
        style={{
          margin: '0 0 0.75rem',
          paddingRight: '1.15rem',
          fontSize: '0.82rem',
          lineHeight: 1.7,
          color: '#78350f',
        }}
      >
        <li>خروجی فعالیت‌های {activitiesLabel} (بالا) را به‌صورت PDF بگیرید.</li>
        <li>فایل را با واتساپ، بل یا ایمیل برای مدیر مارکتینگ ارسال کنید.</li>
        <li>پس از ارسال، گزینهٔ تأیید پایین را تیک بزنید و فرم را ثبت کنید.</li>
      </ol>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '0.85rem' }}>
        <button
          type="button"
          className="btn btn-primary btn-sm"
          data-testid="marketing-campaign-download-pdf"
          disabled={busy || !instanceId || disabled}
          onClick={downloadPdf}
        >
          {busy ? 'در حال آماده‌سازی…' : 'دانلود PDF فعالیت‌ها'}
        </button>
        <button type="button" className="btn btn-outline btn-sm" disabled={disabled} onClick={openWhatsApp}>
          واتساپ
        </button>
        <button type="button" className="btn btn-outline btn-sm" disabled={disabled} onClick={openBale}>
          بل
        </button>
        <button type="button" className="btn btn-outline btn-sm" disabled={disabled} onClick={openEmail}>
          ایمیل
        </button>
      </div>

      <label
        className="psf-field psf-check"
        style={{
          display: 'flex',
          gap: '0.5rem',
          alignItems: 'flex-start',
          marginBottom: '0.65rem',
          cursor: disabled ? 'default' : 'pointer',
        }}
        data-testid="marketing-info-sent-checkbox"
      >
        <input
          type="checkbox"
          checked={sentChecked}
          disabled={disabled}
          onChange={(e) => patchValues({ marketing_info_sent_to_manager: e.target.checked })}
          style={{ marginTop: '0.2rem', flexShrink: 0 }}
        />
        <span style={{ fontSize: '0.85rem', lineHeight: 1.6, color: '#1e293b' }}>
          {sentLabel}
          {sentRequired ? <span style={{ color: '#b91c1c' }}> *</span> : null}
        </span>
      </label>

      <label className="psf-field" htmlFor="marketing-handoff-notes">
        <span className="psf-label">{notesLabel}</span>
        <textarea
          id="marketing-handoff-notes"
          className="psf-textarea"
          rows={3}
          disabled={disabled}
          value={notesValue}
          onChange={(e) => patchValues({ marketing_notes: e.target.value })}
          placeholder="مثلاً زمان ارسال یا کانال ارتباطی (واتساپ، بل، ایمیل)"
        />
      </label>
    </div>
  )
}
