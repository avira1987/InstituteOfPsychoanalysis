import React, { useCallback, useState } from 'react'
import { paymentApi } from '../services/api'

function formatRial(n) {
  try {
    return Number(n).toLocaleString('fa-IR')
  } catch {
    return String(n)
  }
}

/**
 * پنل مشترک پرداخت درگاه سپ (سامان) — مبلغ به ریال مطابق شاپرک.
 */
export default function SepPaymentPanel({
  instanceId,
  studentId,
  amountRial,
  description = 'پرداخت هزینه جلسه',
  mobile,
}) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const base = (import.meta.env.BASE_URL || '/').replace(/\/$/, '')
  const logoSrc = `${base}/sep-saman-logo.png`

  const goPay = useCallback(async () => {
    setError(null)
    if (!instanceId || !studentId || !amountRial || amountRial < 1000) {
      setError('اطلاعات پرداخت ناقص است؛ صفحه را تازه کنید یا با پشتیبانی تماس بگیرید.')
      return
    }
    const referenceId =
      typeof crypto !== 'undefined' && crypto.randomUUID
        ? crypto.randomUUID().replace(/-/g, '').slice(0, 16)
        : `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 10)}`.slice(0, 16)
    setLoading(true)
    try {
      const { data } = await paymentApi.create({
        amount: Math.round(Number(amountRial)),
        description,
        student_id: studentId,
        instance_id: instanceId,
        reference_id: referenceId,
        mobile: mobile || undefined,
      })
      if (data?.success && data.payment_url) {
        window.location.href = data.payment_url
        return
      }
      setError(data?.detail || 'پاسخ درگاه نامعتبر بود')
    } catch (e) {
      const d = e.response?.data?.detail
      setError(typeof d === 'string' ? d : e.message || 'خطا در اتصال به درگاه')
    } finally {
      setLoading(false)
    }
  }, [amountRial, description, instanceId, mobile, studentId])

  if (amountRial == null || Number(amountRial) < 1000) {
    return (
      <div
        className="sep-payment-panel sep-payment-panel--warn"
        style={{
          marginTop: '1rem',
          padding: '1rem 1.25rem',
          borderRadius: '12px',
          border: '1px solid #fcd34d',
          background: 'linear-gradient(135deg, #fffbeb 0%, #fff 100%)',
          fontSize: '0.9rem',
          lineHeight: 1.65,
        }}
      >
        <strong>پرداخت درگاه</strong>
        <p style={{ margin: '0.5rem 0 0' }}>
          مبلغ قابل پرداخت (ریال) در پروندهٔ این مرحله ثبت نشده. صفحه را یک‌بار تازه کنید؛ اگر برطرف نشد با پشتیبانی تماس بگیرید.
        </p>
      </div>
    )
  }

  return (
    <div
      className="sep-payment-panel card"
      style={{
        marginTop: '1rem',
        padding: '1.25rem',
        borderRadius: '12px',
        border: '1px solid #e5e7eb',
        background: 'linear-gradient(165deg, #f8fafc 0%, #ffffff 55%)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
        <img
          src={logoSrc}
          alt="درگاه پرداخت اینترنتی سپ بانک سامان"
          style={{ maxHeight: '52px', width: 'auto', objectFit: 'contain' }}
        />
        <div style={{ flex: '1 1 12rem' }}>
          <h3 style={{ margin: 0, fontSize: '1.05rem', fontWeight: 700 }}>پرداخت از طریق درگاه سپ</h3>
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.88rem', color: '#64748b', lineHeight: 1.6 }}>
            پرداخت امن اینترنتی به‌پرداخت ملت (سپ). پس از کلیک، به صفحهٔ بانک هدایت می‌شوید.
          </p>
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.95rem', fontWeight: 600 }}>
            مبلغ قابل پرداخت:{' '}
            <span dir="ltr" style={{ unicodeBidi: 'embed' }}>
              {formatRial(amountRial)}
            </span>{' '}
            ریال
          </p>
        </div>
      </div>
      {error && (
        <p style={{ color: '#b91c1c', fontSize: '0.88rem', marginTop: '0.75rem', marginBottom: 0 }} role="alert">
          {error}
        </p>
      )}
      <div style={{ marginTop: '1rem' }}>
        <button
          type="button"
          className="btn btn-primary"
          disabled={loading}
          onClick={goPay}
          data-testid="sep-payment-submit"
        >
          {loading ? 'در حال اتصال…' : 'ورود به درگاه پرداخت'}
        </button>
      </div>
    </div>
  )
}
