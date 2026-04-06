import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../services/api'

const STATE_TYPE_LABELS = {
  initial: 'شروع',
  intermediate: 'در حال انجام',
  terminal: 'پایان',
}

const STATE_TYPE_COLORS = {
  initial: 'success',
  intermediate: 'info',
  terminal: 'primary',
}

const CONDITIONS = [
  {
    title: 'شرایط پذیرش دوره مقدماتی',
    items: [
      'دارا بودن حداقل مدرک کارشناسی در رشته‌های مرتبط (روان‌شناسی، مشاوره، پزشکی و ...)',
      'ارائه رزومه تحصیلی و حرفه‌ای',
      'موفقیت در مصاحبه ورودی',
      'تعهد به حضور منظم در جلسات',
    ],
  },
  {
    title: 'شرایط پذیرش دوره جامع',
    items: [
      'اتمام موفقیت‌آمیز دوره مقدماتی یا معادل آن',
      'دارا بودن مدرک کارشناسی ارشد یا بالاتر',
      'تأیید کمیته پذیرش انیستیتو',
      'گذراندن مصاحبه تخصصی',
      'شروع روان‌درمانی فردی (تحلیلی)',
    ],
  },
]

export default function ProcessesInfo() {
  const [processes, setProcesses] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    publicApi.processes()
      .then(r => setProcesses(r.data.processes || []))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <div className="pub-page-header">
        <h1>فرآیندها و مراحل آموزشی</h1>
        <p>آشنایی با مراحل پذیرش، شرایط و فرآیندهای تعریف‌شده در سامانه — همان فرآیندهایی که پس از پذیرش در پنل قابل پیگیری هستند</p>
      </div>

      {/* ─── Conditions ─── */}
      <section className="pub-section">
        <div className="pub-section-header">
          <div className="pub-section-badge">شرایط پذیرش</div>
          <h2>شرایط و پیش‌نیازها</h2>
          <p>پیش از ثبت‌نام، شرایط زیر را بررسی کنید</p>
        </div>

        <div className="pub-info-grid">
          {CONDITIONS.map((cond, i) => (
            <div key={i} className="pub-info-card">
              <h3>📋 {cond.title}</h3>
              <ul>
                {cond.items.map((item, j) => (
                  <li key={j}>{item}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>

      {/* ─── Process List ─── */}
      <section className="pub-section" style={{ paddingTop: 0 }}>
        <div className="pub-section-header">
          <div className="pub-section-badge">فرآیندهای سیستم</div>
          <h2>فرآیندهای فعال</h2>
          <p>فرآیندهای تعریف شده در سامانه و مراحل هر کدام</p>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: '3rem' }}>
            <div className="loading-spinner" style={{ margin: '0 auto' }} />
          </div>
        ) : processes.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '3rem', color: 'var(--text-secondary)' }}>
            هنوز فرآیندی تعریف نشده است.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
            {processes.map((proc) => (
              <div key={proc.code} className="pub-info-card">
                <h3 style={{ fontSize: '1.2rem', marginBottom: '0.5rem' }}>
                  {proc.name_fa || proc.code}
                </h3>
                {proc.description && (
                  <p style={{ marginBottom: '1rem' }}>{proc.description}</p>
                )}
                <div style={{ fontSize: '0.85rem', color: 'var(--text-light)', marginBottom: '1rem' }}>
                  تعداد مراحل: {proc.states_count}
                </div>

                {proc.states && proc.states.length > 0 && (
                  <div className="pub-process-timeline">
                    {proc.states.map((state, idx) => (
                      <div key={state.code} className="pub-process-step">
                        <div className={`pub-process-dot ${state.state_type || 'intermediate'}`}>
                          {idx + 1}
                        </div>
                        <div className="pub-process-info">
                          <h4>{state.name_fa || state.code}</h4>
                          <span className={`badge badge-${STATE_TYPE_COLORS[state.state_type] || 'info'}`}>
                            {STATE_TYPE_LABELS[state.state_type] || state.state_type}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ─── CTA ─── */}
      <section className="pub-section" style={{ paddingTop: 0 }}>
        <div className="pub-cta">
          <h2>شرایط لازم را دارید؟</h2>
          <p>همین حالا ثبت‌نام کنید یا وارد پنل شوید تا فرایندهای خود را از بخش «فرایندها» مدیریت کنید.</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', justifyContent: 'center' }}>
            <Link to="/register" className="pub-cta-btn">
              ثبت‌نام دانشجو
            </Link>
            <Link to="/login" className="pub-cta-btn" style={{ background: 'transparent', border: '2px solid currentColor' }}>
              ورود به پنل
            </Link>
          </div>
        </div>
      </section>
    </>
  )
}
