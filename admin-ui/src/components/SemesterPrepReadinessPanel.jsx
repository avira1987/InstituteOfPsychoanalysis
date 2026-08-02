import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { semesterPrepApi } from '../services/api'

function ReadinessStatusIcon({ complete }) {
  if (complete) {
    return (
      <span aria-hidden style={{ color: '#15803d', fontWeight: 700 }}>
        ✓
      </span>
    )
  }
  return (
    <span aria-hidden style={{ color: '#ca8a04', fontWeight: 700 }}>
      !
    </span>
  )
}

function actionHref(item) {
  const base = item?.action_route || '/panel/semester-prep/readiness'
  const anchor = item?.action_anchor
  if (anchor && base.includes('/readiness')) {
    return `${base}#${anchor}`
  }
  if (item?.key === 'license') {
    return '/panel/semester-prep/workbench?process_code=fall_semester_preparation'
  }
  return base
}

export default function SemesterPrepReadinessPanel({
  readiness: readinessProp,
  onReload,
  compact = false,
  showTitle = true,
}) {
  const [readiness, setReadiness] = useState(readinessProp || null)
  const [loading, setLoading] = useState(!readinessProp)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await semesterPrepApi.getReadiness()
      setReadiness(res.data)
      onReload?.(res.data)
    } catch {
      setReadiness(null)
    } finally {
      setLoading(false)
    }
  }, [onReload])

  useEffect(() => {
    if (readinessProp) {
      setReadiness(readinessProp)
      setLoading(false)
      return undefined
    }
    load()
    return undefined
  }, [readinessProp, load])

  if (loading && !readiness) {
    return <p className="muted">در حال بررسی آمادگی پیش‌نیازها…</p>
  }

  if (!readiness) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        وضعیت آمادگی در دسترس نیست.
      </p>
    )
  }

  const items = readiness.items || []
  const incomplete = readiness.incomplete_count || 0

  return (
    <section
      data-testid="semester-prep-readiness-panel"
      style={{
        border: incomplete > 0 ? '1px solid #fde68a' : '1px solid #bbf7d0',
        background: incomplete > 0 ? '#fffbeb' : '#f0fdf4',
        borderRadius: '10px',
        padding: compact ? '0.85rem 1rem' : '1rem 1.15rem',
        marginBottom: compact ? 0 : '1.25rem',
      }}
    >
      {showTitle ? (
        <h2 style={{ fontSize: compact ? '1rem' : '1.05rem', margin: '0 0 0.5rem' }}>
          آمادگی پیش‌نیازهای آماده‌سازی ترم
        </h2>
      ) : null}
      <p style={{ margin: '0 0 0.85rem', fontSize: '0.88rem', lineHeight: 1.65, color: '#475569' }}>
        {readiness.ready
          ? 'همهٔ پیش‌نیازهای توصیه‌شده تکمیل شده‌اند.'
          : `${incomplete} مورد هنوز تکمیل نشده — می‌توانید فرایند را ادامه دهید؛ تکمیل این موارد کیفیت فرم‌ها را بهتر می‌کند.`}
      </p>
      <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
        {items.map((item) => (
          <li
            key={item.key}
            style={{
              display: 'flex',
              alignItems: 'flex-start',
              justifyContent: 'space-between',
              gap: '0.75rem',
              padding: '0.55rem 0.65rem',
              background: '#fff',
              borderRadius: '8px',
              border: '1px solid #e2e8f0',
            }}
          >
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', marginBottom: '0.2rem' }}>
                <ReadinessStatusIcon complete={item.complete} />
                <strong style={{ fontSize: '0.9rem' }}>{item.title_fa}</strong>
                {typeof item.count === 'number' ? (
                  <span className="muted" style={{ fontSize: '0.78rem' }}>
                    ({item.count})
                  </span>
                ) : null}
              </div>
              <p style={{ margin: 0, fontSize: '0.82rem', color: '#64748b', lineHeight: 1.6 }}>
                {item.message_fa}
              </p>
            </div>
            {!item.complete ? (
              <Link
                to={actionHref(item)}
                className="btn btn-secondary btn-sm"
                style={{ whiteSpace: 'nowrap', fontSize: '0.78rem' }}
              >
                تکمیل
              </Link>
            ) : null}
          </li>
        ))}
      </ul>
      {!readinessProp || onReload ? (
        <button
          type="button"
          className="btn btn-outline btn-sm"
          style={{ marginTop: '0.75rem' }}
          onClick={() => (onReload ? onReload() : load())}
        >
          به‌روزرسانی وضعیت
        </button>
      ) : null}
    </section>
  )
}
