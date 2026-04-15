import React, { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { publicApi } from '../../services/api'

export default function StudentLifecycleMatrix() {
  const [payload, setPayload] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    publicApi
      .studentLifecycleMatrix()
      .then((r) => setPayload(r.data))
      .catch(() =>
        setError('خطا در بارگذاری اطلاعات. لطفاً اتصال اینترنت را بررسی کرده و دوباره تلاش کنید.'),
      )
      .finally(() => setLoading(false))
  }, [])

  const roleLabel = (role) => (payload?.role_labels_fa && payload.role_labels_fa[role]) || 'نقش کاربری'

  return (
    <>
      <div className="pub-page-header">
        <h1 data-testid="lifecycle-page-title">مسیر آموزشی شما از ورود تا پایان دوره</h1>
        <p style={{ lineHeight: 1.75 }}>
          این صفحه فقط <b>نقشهٔ کلی</b> را نشان می‌دهد: معمولاً در هر مرحله چه اتفاقی می‌افتد و{' '}
          <b>چه کسانی</b> در سامانه در کنار شما کار می‌کنند. نیازی به یاد گرفتن نام‌های فنی یا جزئیات
          سامانه نیست؛ کافی است تصویر بزرگ را ببینید تا بدانید تقریباً کجای مسیر هستید و بعدش چه چیزهایی ممکن
          است پیش بیاید. برای کارهای دقیق همان روز، همیشه به <b>پنل خودتان</b> و{' '}
          <Link to="/guide">راهنمای سامانه</Link> مراجعه کنید.
        </p>
        {payload?.stats && (
          <p style={{ marginTop: '0.75rem', fontSize: '0.95rem', opacity: 0.9 }} data-testid="lifecycle-intro-note">
            این مسیر در چند بخش اصلی تقسیم شده است؛ تعداد دقیق مراحل برای هر نفر ممکن است فرق کند.
          </p>
        )}
      </div>

      {loading && (
        <div className="pub-section" data-testid="lifecycle-loading">
          <p>در حال بارگذاری…</p>
        </div>
      )}

      {error && (
        <div
          className="pub-section"
          style={{ borderColor: '#fecaca', background: '#fef2f2' }}
          data-testid="lifecycle-error"
        >
          <p>{error}</p>
        </div>
      )}

      {payload && !loading && (
        <div data-testid="lifecycle-matrix-root">
          <section className="pub-section">
            <div className="pub-section-header">
              <div className="pub-section-badge">مراحل</div>
              <h2>مراحل اصلی مسیر</h2>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.95rem', color: 'var(--text-secondary, #64748b)' }}>
                هر بخش چه معنی‌ای برای شما دارد
              </p>
            </div>
            <div className="pub-info-grid">
              {(payload.phases || []).map((phase) => (
                <div
                  key={phase.phase_id}
                  className="pub-info-card"
                  data-testid={`lifecycle-phase-${phase.phase_id}`}
                >
                  <h3>{phase.title_fa}</h3>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <b style={{ fontSize: '0.9rem' }}>مثال: ممکن است در این مرحله…</b>
                    <ul style={{ marginTop: '0.35rem' }}>
                      {(phase.student_state_hints || []).map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <b style={{ fontSize: '0.9rem' }}>کارهایی که ممکن است در سامانه ثبت شود</b>
                    <ul
                      className="lifecycle-process-list"
                      style={{
                        marginTop: '0.35rem',
                        fontSize: '0.9rem',
                        lineHeight: 1.65,
                      }}
                    >
                      {(phase.process_codes || []).map((code, idx) => {
                        const labels = phase.process_labels_fa || []
                        const text = labels[idx] || 'فرایند ثبت‌شده در سامانه'
                        return (
                          <li key={code} data-testid={`lifecycle-process-${code}`}>
                            {text}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="pub-section" style={{ paddingTop: 0 }}>
            <div className="pub-section-header">
              <div className="pub-section-badge">نقش‌ها</div>
              <h2>هر نقش معمولاً چه کاری انجام می‌دهد؟</h2>
              <p style={{ margin: '0.25rem 0 0', fontSize: '0.95rem', color: 'var(--text-secondary, #64748b)' }}>
                این‌ها نقش‌های سازمانی در سامانه‌اند؛ لازم نیست حفظ کنید. فقط بدانید گاهی باید با چه کسانی هماهنگ
                شوید.
              </p>
            </div>
            <div className="pub-info-grid">
              {(payload.roles_order || []).map((role) => {
                const items = (payload.role_action_patterns || {})[role] || []
                if (!items.length) return null
                return (
                  <div key={role} className="pub-info-card" data-testid={`lifecycle-role-${role}`}>
                    <h3>{roleLabel(role)}</h3>
                    <ul>
                      {items.map((line, j) => (
                        <li key={j}>{line}</li>
                      ))}
                    </ul>
                  </div>
                )
              })}
            </div>
          </section>

          <div style={{ textAlign: 'center', marginTop: '1rem', marginBottom: '2rem' }}>
            <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary, #64748b)', marginBottom: '0.75rem' }}>
              برای قدم‌به‌قدم استفاده از سامانه:
            </p>
            <Link to="/guide">راهنمای سامانه</Link>
            {' · '}
            <Link to="/">خانه</Link>
          </div>
        </div>
      )}
    </>
  )
}
