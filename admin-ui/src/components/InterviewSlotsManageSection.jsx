import React, { useCallback, useEffect, useState } from 'react'
import { interviewSlotsApi } from '../services/api'
import InterviewBookingsPanel from './InterviewBookingsPanel'
import InterviewSlotRecurringRules from './InterviewSlotRecurringRules'
import InterviewSlotsAdmin from './InterviewSlotsAdmin'

function RecurringRulesIntroModal({ onConfirm, onCancel }) {
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="recurring-rules-intro-title"
      data-testid="recurring-rules-intro-modal"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 1200,
        background: 'rgba(15, 23, 42, 0.45)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onCancel()
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '32rem',
          background: '#fff',
          borderRadius: '12px',
          padding: '1.25rem 1.5rem',
          boxShadow: '0 20px 40px rgba(0,0,0,0.15)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="recurring-rules-intro-title" style={{ margin: '0 0 0.75rem', fontSize: '1.05rem' }}>
          الگوی زمانی تکراری — چه زمانی استفاده شود؟
        </h3>
        <p className="muted" style={{ margin: '0 0 0.85rem', fontSize: '0.88rem', lineHeight: 1.65 }}>
          در بیشتر موارد، ثبت <strong>یک وقت مشخص</strong> در بخش «تعریف وقت مصاحبه» کافی است.
          الگوی تکراری فقط وقتی مناسب است که:
        </p>
        <ul
          style={{
            margin: '0 0 1rem',
            paddingRight: '1.25rem',
            fontSize: '0.88rem',
            lineHeight: 1.7,
            color: 'var(--text-secondary)',
          }}
        >
          <li>هر هفته روز و ساعت ثابتی برای مصاحبه دارید (مثلاً هر شنبه ۱۰ تا ۱۱).</li>
          <li>می‌خواهید سامانه خودکار برای چند هفته آینده وقت آزاد بسازد.</li>
          <li>نمی‌خواهید هر هفته دستی وقت تکی ثبت کنید.</li>
        </ul>
        <p className="muted" style={{ margin: '0 0 1.1rem', fontSize: '0.82rem', lineHeight: 1.6 }}>
          برای تاریخ یا ساعت استثنا، همان «تعریف وقت مصاحبه» را استفاده کنید؛ الگو و ثبت دستی با هم تداخل ندارند.
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', justifyContent: 'flex-end' }}>
          <button type="button" className="btn btn-outline" onClick={onCancel} data-testid="recurring-rules-intro-cancel">
            انصراف
          </button>
          <button type="button" className="btn btn-primary" onClick={onConfirm} data-testid="recurring-rules-intro-confirm">
            ادامه — باز کردن تنظیمات الگو
          </button>
        </div>
      </div>
    </div>
  )
}

/**
 * تعریف وقت مصاحبه (اصلی) + الگوی تکراری (پنهان تا تأیید راهنما) + رزروها.
 */
export default function InterviewSlotsManageSection({
  showToast,
  onCapacityChanged,
  showBookings = true,
  slotDefaults = null,
  interviewerRoster = null,
  semesterPrepMode = false,
}) {
  const [recurringExpanded, setRecurringExpanded] = useState(false)
  const [introOpen, setIntroOpen] = useState(false)
  const [rulesCount, setRulesCount] = useState(null)

  const refreshRulesCount = useCallback(() => {
    interviewSlotsApi
      .recurringRulesList()
      .then((r) => setRulesCount((r.data?.rules || []).length))
      .catch(() => setRulesCount(null))
  }, [])

  useEffect(() => {
    refreshRulesCount()
  }, [refreshRulesCount])

  const handleCapacityChanged = useCallback(() => {
    refreshRulesCount()
    onCapacityChanged?.()
  }, [onCapacityChanged, refreshRulesCount])

  const requestExpandRecurring = () => {
    setIntroOpen(true)
  }

  const confirmExpandRecurring = () => {
    setIntroOpen(false)
    setRecurringExpanded(true)
  }

  const collapseRecurring = () => {
    setRecurringExpanded(false)
  }

  return (
    <>
      <InterviewSlotsAdmin
        showToast={showToast}
        onCapacityChanged={handleCapacityChanged}
        slotDefaults={slotDefaults}
        interviewerRoster={interviewerRoster}
        semesterPrepMode={semesterPrepMode}
      />

      {!recurringExpanded ? (
        <div
          style={{
            marginBottom: '1.5rem',
            padding: '0.7rem 1rem',
            borderRadius: '10px',
            border: '1px dashed #cbd5e1',
            background: '#f8fafc',
          }}
          data-testid="interview-recurring-rules-collapsed"
        >
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '0.65rem',
            }}
          >
            <div style={{ flex: '1 1 14rem', minWidth: 0 }}>
              <div style={{ fontSize: '0.82rem', fontWeight: 600, color: '#64748b' }}>
                گزینهٔ پیشرفته (بسته)
              </div>
              <p className="muted" style={{ margin: '0.25rem 0 0', fontSize: '0.84rem', lineHeight: 1.55 }}>
                الگوی هفتگی خودکار — برای ثبت وقت معمولاً فقط فرم «تعریف وقت مصاحبه» بالا را پر کنید.
                {rulesCount != null && rulesCount > 0 && (
                  <>
                    {' '}
                    (<strong>{rulesCount.toLocaleString('fa-IR')}</strong> الگوی فعال دارید.)
                  </>
                )}
              </p>
            </div>
            <button
              type="button"
              className="btn btn-outline btn-sm"
              onClick={requestExpandRecurring}
              data-testid="interview-recurring-rules-expand"
            >
              {rulesCount != null && rulesCount > 0 ? 'ویرایش الگوها' : 'باز کردن الگوی تکراری'}
            </button>
          </div>
        </div>
      ) : (
        <div data-testid="interview-recurring-rules-expanded">
          <div
            style={{
              display: 'flex',
              justifyContent: 'flex-end',
              marginBottom: '0.35rem',
              padding: '0 0.15rem',
            }}
          >
            <button
              type="button"
              className="btn btn-link btn-sm"
              onClick={collapseRecurring}
              data-testid="interview-recurring-rules-collapse"
              style={{ fontSize: '0.82rem' }}
            >
              بستن بخش الگوی تکراری
            </button>
          </div>
          <InterviewSlotRecurringRules showToast={showToast} onCapacityChanged={handleCapacityChanged} />
        </div>
      )}

      {introOpen ? (
        <RecurringRulesIntroModal onConfirm={confirmExpandRecurring} onCancel={() => setIntroOpen(false)} />
      ) : null}

      {showBookings ? <InterviewBookingsPanel showToast={showToast} /> : null}
    </>
  )
}
