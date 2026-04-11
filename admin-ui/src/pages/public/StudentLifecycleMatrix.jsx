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
      .catch((e) => setError(e?.message || 'خطا در بارگذاری'))
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <div className="pub-page-header">
        <h1 data-testid="lifecycle-page-title">چرخه عمر دانشجو و اقدام نقش‌ها</h1>
        <p>
          نمایش فازهای آموزشی از ثبت‌نام تا فارغ‌التحصیلی، فرایندهای مرتبط در رجیستری، و الگوی اقدام برای
          هر نقش — برای آموزش تیم و اتوماسیون وب.
        </p>
        {payload?.stats && (
          <p style={{ marginTop: '0.75rem', fontSize: '0.95rem', opacity: 0.9 }}>
            <span data-testid="lifecycle-stat-phases">{payload.stats.phase_count}</span> فاز،{' '}
            <span data-testid="lifecycle-stat-processes">{payload.stats.unique_process_codes}</span> نوع فرایند
            منحصربه‌فرد، جمع پیشنهادی حدود{' '}
            <span data-testid="lifecycle-stat-demo">{payload.stats.suggested_total_demo_students}</span> دانشجوی
            نمونه در سناریوهای دمو.
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
              <div className="pub-section-badge">فازها</div>
              <h2>فازها و فرایندهای رجیستری</h2>
            </div>
            <div className="pub-info-grid">
              {(payload.phases || []).map((phase) => (
                <div
                  key={phase.phase_id}
                  className="pub-info-card"
                  data-testid={`lifecycle-phase-${phase.phase_id}`}
                >
                  <h3>{phase.title_fa}</h3>
                  <p style={{ fontSize: '0.85rem', color: '#64748b', marginBottom: '0.5rem' }}>
                    پیشنهاد دمو:{' '}
                    <strong data-testid={`lifecycle-demo-count-${phase.phase_id}`}>
                      {phase.demo_student_count_hint}
                    </strong>{' '}
                    دانشجو
                  </p>
                  <div style={{ marginBottom: '0.75rem' }}>
                    <strong style={{ fontSize: '0.9rem' }}>نمونه وضعیت دانشجو</strong>
                    <ul style={{ marginTop: '0.35rem' }}>
                      {(phase.student_state_hints || []).map((h, i) => (
                        <li key={i}>{h}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <strong style={{ fontSize: '0.9rem' }}>کدهای فرایند</strong>
                    <ul
                      className="lifecycle-process-codes"
                      style={{
                        marginTop: '0.35rem',
                        fontFamily: 'ui-monospace, monospace',
                        fontSize: '0.82rem',
                        direction: 'ltr',
                        textAlign: 'left',
                      }}
                    >
                      {(phase.process_codes || []).map((code) => (
                        <li key={code} data-testid={`lifecycle-process-${code}`}>
                          {code}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="pub-section" style={{ paddingTop: 0 }}>
            <div className="pub-section-header">
              <div className="pub-section-badge">نقش‌ها</div>
              <h2>الگوی اقدام به تفکیک نقش</h2>
            </div>
            <div className="pub-info-grid">
              {(payload.roles_order || []).map((role) => {
                const items = (payload.role_action_patterns || {})[role] || []
                if (!items.length) return null
                return (
                  <div key={role} className="pub-info-card" data-testid={`lifecycle-role-${role}`}>
                    <h3 style={{ direction: 'ltr', textAlign: 'right' }}>{role}</h3>
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
            <Link to="/guide">راهنمای سامانه</Link>
            {' · '}
            <Link to="/">خانه</Link>
          </div>
        </div>
      )}
    </>
  )
}
