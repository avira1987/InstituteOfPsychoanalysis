import React, { useCallback, useEffect, useState } from 'react'
import { therapyApi } from '../services/api'
import { formatShamsiTehran } from '../utils/shamsiDateTime'

const SCENARIO_TONE = {
  scenario_1_credit_returned: { bg: '#f0fdf4', border: '#16a34a', text: '#14532d' },
  scenario_2_no_action: { bg: '#f8fafc', border: '#64748b', text: '#334155' },
  scenario_3_forfeited: { bg: '#fef2f2', border: '#dc2626', text: '#991b1b' },
  scenario_4_debt_created: { bg: '#fff7ed', border: '#ea580c', text: '#9a3412' },
  excluded: { bg: '#eff6ff', border: '#2563eb', text: '#1d4ed8' },
  triggered: { bg: '#fefce8', border: '#ca8a04', text: '#854d0e' },
}

function fmtDate(iso) {
  if (!iso) return '—'
  try {
    return formatShamsiTehran(iso)
  } catch {
    return iso
  }
}

function StatTile({ label, value, bg, border, text }) {
  return (
    <div style={{ padding: '0.85rem', borderRadius: '10px', background: bg, borderRight: `4px solid ${border}` }}>
      <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{label}</div>
      <div style={{ fontSize: '1.4rem', fontWeight: 800, color: text }}>{value}</div>
    </div>
  )
}

/**
 * داشبورد تعیین تکلیف هزینه جلسه — فرایند ۷ (fee_determination) — نمای دانشجو.
 *
 * فرایند کاملاً خودکار است؛ این پنل صرفاً سهمیهٔ غیبت سالانه و نتیجهٔ ۴ سناریوی
 * مالی (بازگشت اعتبار / بدون اقدام / مصادره / بدهی) را به‌صورت فقط‌خواندنی نشان می‌دهد.
 */
export default function StudentFeeDeterminationPanel({ active = true, compact = false }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await therapyApi.myFeeDeterminationSummary()
      setData(res.data)
    } catch (e) {
      setData(null)
      setError(e.response?.data?.detail || 'بارگذاری تعیین تکلیف هزینه جلسات ممکن نشد.')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (active) load()
  }, [active, load])

  if (!active && !data) return null

  if (loading && !data) {
    return (
      <div className="card" data-testid="student-fee-determination-panel">
        <div style={{ padding: '1.5rem', textAlign: 'center', fontSize: '0.9rem' }}>در حال بارگذاری…</div>
      </div>
    )
  }

  if (error && !data) {
    return (
      <div className="card" data-testid="student-fee-determination-panel">
        <div className="card-header">
          <h3 className="card-title">تعیین تکلیف هزینه جلسات</h3>
        </div>
        <div style={{ padding: '0 1rem 1rem', color: 'var(--danger)' }}>{error}</div>
      </div>
    )
  }

  const quota = Number(data?.absence_quota ?? 0)
  const used = Number(data?.absences_used ?? 0)
  const remaining = Number(data?.remaining_quota ?? 0)
  const exceeded = Boolean(data?.quota_exceeded)
  const outcomes = (data?.outcomes || []).slice(0, compact ? 4 : 15)

  return (
    <div className="card" data-testid="student-fee-determination-panel">
      <div className="card-header">
        <h3 className="card-title">تعیین تکلیف هزینه جلسات (فرایند ۷)</h3>
        <button type="button" className="btn btn-outline btn-sm" onClick={load} disabled={loading}>
          {loading ? '…' : 'بروزرسانی'}
        </button>
      </div>

      <div style={{ padding: '0 1rem 1rem' }}>
        <p style={{ margin: '0 0 0.85rem', fontSize: '0.85rem', lineHeight: 1.7, color: 'var(--text-secondary)' }}>
          سهمیهٔ مجاز غیبت/کنسلی هر سال = ۳ × تعداد جلسات هفتگی (ceil). تا پایان سهمیه، در صورت پرداخت
          یک جلسه بستانکار می‌شوید؛ پس از اتمام سهمیه، هزینهٔ پرداخت‌شده مصادره یا بدهی ثبت می‌شود.
        </p>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: compact ? '1fr 1fr' : 'repeat(auto-fit, minmax(140px, 1fr))',
            gap: '0.65rem',
            marginBottom: '0.85rem',
          }}
        >
          <StatTile
            label="سهمیهٔ سالانه"
            value={quota.toLocaleString('fa-IR')}
            bg="#eff6ff"
            border="#2563eb"
            text="#1d4ed8"
          />
          <StatTile
            label="مصرف‌شده"
            value={used.toLocaleString('fa-IR')}
            bg="#f8fafc"
            border="#64748b"
            text="#334155"
          />
          <StatTile
            label="باقی‌مانده"
            value={remaining.toLocaleString('fa-IR')}
            bg={exceeded ? '#fef2f2' : '#f0fdf4'}
            border={exceeded ? '#dc2626' : '#16a34a'}
            text={exceeded ? '#991b1b' : '#14532d'}
          />
          {!compact && (
            <StatTile
              label="جلسات در هفته"
              value={data?.weekly_sessions != null ? Number(data.weekly_sessions).toLocaleString('fa-IR') : '—'}
              bg="#faf5ff"
              border="#9333ea"
              text="#6b21a8"
            />
          )}
        </div>

        {!compact && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(120px, 1fr))',
              gap: '0.5rem',
              marginBottom: '0.85rem',
            }}
          >
            <StatTile
              label="بازگشت اعتبار"
              value={Number(data?.credit_returned_count ?? 0).toLocaleString('fa-IR')}
              bg="#f0fdf4"
              border="#16a34a"
              text="#14532d"
            />
            <StatTile
              label="مصادره"
              value={Number(data?.forfeited_count ?? 0).toLocaleString('fa-IR')}
              bg="#fef2f2"
              border="#dc2626"
              text="#991b1b"
            />
            <StatTile
              label="بدهی ایجادشده"
              value={Number(data?.debt_created_count ?? 0).toLocaleString('fa-IR')}
              bg="#fff7ed"
              border="#ea580c"
              text="#9a3412"
            />
          </div>
        )}

        {exceeded && (
          <div
            style={{
              padding: '0.6rem 0.8rem',
              borderRadius: '8px',
              background: '#fef2f2',
              color: '#991b1b',
              fontSize: '0.82rem',
              lineHeight: 1.6,
              marginBottom: '0.85rem',
            }}
          >
            سهمیهٔ غیبت سالانهٔ شما به پایان رسیده است. غیبت/کنسلی‌های بعدی مشمول مصادره هزینه یا ایجاد بدهی خواهند بود.
          </div>
        )}

        {outcomes.length > 0 ? (
          <>
            <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.5rem' }}>سوابق تعیین تکلیف</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
              {outcomes.map((o) => {
                const tone = SCENARIO_TONE[o.state] || SCENARIO_TONE.excluded
                return (
                  <div
                    key={o.instance_id}
                    style={{
                      padding: '0.55rem 0.7rem',
                      borderRadius: '8px',
                      background: tone.bg,
                      borderRight: `4px solid ${tone.border}`,
                      fontSize: '0.82rem',
                    }}
                  >
                    <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'space-between', gap: '0.35rem' }}>
                      <strong style={{ color: tone.text }}>{o.state_fa}</strong>
                      <span style={{ color: '#64748b' }}>{fmtDate(o.session_date || o.completed_at || o.started_at)}</span>
                    </div>
                    {o.summary_fa && (
                      <div style={{ marginTop: '0.3rem', color: '#475569', lineHeight: 1.6 }}>{o.summary_fa}</div>
                    )}
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.82rem', color: '#94a3b8' }}>
            هنوز موردی برای تعیین تکلیف هزینه ثبت نشده است.
          </p>
        )}

        <p style={{ margin: '0.85rem 0 0', fontSize: '0.78rem', color: '#94a3b8', lineHeight: 1.6 }}>
          این فرایند به‌صورت خودکار پس از ثبت غیبت توسط درمانگر یا کنسل جلسه توسط شما اجرا می‌شود و نیازی به اقدام دستی ندارد.
        </p>
      </div>
    </div>
  )
}
