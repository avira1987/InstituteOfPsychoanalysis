import React from 'react'
import { buildRoadmapStates } from '../utils/studentRoadmap'
import { buildStudentGuidance } from '../utils/studentProcessGuidance'
import ProcessStepForms from './ProcessStepForms'
import StudentProcessGuidancePanel from './StudentProcessGuidancePanel'
import { filterFormsForStudent, stepFormsBlockTransition } from '../utils/processFormsStudent'
import { labelProcess, labelState } from '../utils/processDisplay'

/**
 * کارت «قدم بعد» — فرم‌های مرحله + فقط اقدامات مجاز از API انتقال + مسیر بازی‌گونه
 */
export default function StudentQuestCard({
  loading,
  detail,
  definition,
  transitions,
  forms,
  stepFormValues,
  onStepFieldChange,
  onFormRegisterSubmit,
  decisionNotes,
  onDecisionNotesChange,
  onTrigger,
  onOpenProcesses,
  extraData,
  /** پس از ثبت موفق فرم در سرور؛ تا باز شدن توسط مسئول فرم مخفی است */
  stepFormLocked = false,
}) {
  const roadmapStates = definition ? buildRoadmapStates(definition) : []
  const curIdx = detail && roadmapStates.length
    ? roadmapStates.findIndex(s => s.code === detail.current_state)
    : -1
  const stepIndex = curIdx >= 0 ? curIdx + 1 : 0
  const totalSteps = roadmapStates.length || 1
  const pathPct = roadmapStates.length && curIdx >= 0
    ? Math.min(100, Math.round(((curIdx + 1) / roadmapStates.length) * 100))
    : 0

  const currentStateLabel = roadmapStates.find(s => s.code === detail?.current_state)?.name_fa
    || labelState(detail?.current_state)
    || '—'

  const level = extraData?.gamification?.level

  if (loading) {
    return (
      <div className="quest-card quest-card--loading">
        <div className="quest-card-shimmer" />
        <p className="quest-loading-text">در حال بارگذاری مسیر اصلی شما…</p>
      </div>
    )
  }

  if (!detail) {
    return (
      <div className="quest-card quest-card--empty">
        <div className="quest-card-badge">مسیر</div>
        <h2 className="quest-title">هنوز فرایند اصلی به پروفایل شما وصل نیست</h2>
        <p className="quest-desc">
          معمولاً پس از ثبت‌نام، مسیر ثبت‌نام دوره به‌صورت خودکار باز می‌شود. اگر این پیام را می‌بینید، با پشتیبانی یا بخش پذیرش تماس بگیرید.
        </p>
        {onOpenProcesses && (
          <button type="button" className="btn btn-primary" onClick={onOpenProcesses}>
            رفتن به فرایندها
          </button>
        )}
      </div>
    )
  }

  const processTitle = labelProcess(detail.process_code)
  const done = detail.is_completed || detail.is_cancelled
  const studentForms = filterFormsForStudent(forms || [])
  const transitionBlocked = !done && studentForms.length > 0 && !stepFormLocked
    && stepFormsBlockTransition(forms, stepFormValues)
  const guidance = buildStudentGuidance({
    definition,
    detail,
    transitions,
    forms,
    stepFormLocked,
  })

  return (
    <div className="quest-card" data-testid="student-quest-card">
      <div className="quest-card-top">
        <div className="quest-card-head">
          <span className="quest-pill">مسیر فعلی شما</span>
          {level != null && (
            <span className="quest-pill quest-pill--xp">سطح {level}</span>
          )}
        </div>
        <h2 className="quest-title">{processTitle}</h2>
        <p className="quest-sub">
          {done
            ? (detail.is_completed ? 'این مسیر به پایان رسیده است.' : 'این مسیر لغو شده است.')
            : `مرحلهٔ ${stepIndex} از ${totalSteps} · ${pathPct}% مسیر`}
        </p>
      </div>

      <StudentProcessGuidancePanel guidance={guidance} variant="quest" />

      {!done && roadmapStates.length > 0 && (
        <div className="quest-steps" aria-label="مراحل فرایند">
          {roadmapStates.map((st, i) => {
            const isCurrent = st.code === detail.current_state
            const past = curIdx >= 0 && i < curIdx
            return (
              <div
                key={st.code}
                className={`quest-step ${isCurrent ? 'quest-step--current' : ''} ${past ? 'quest-step--past' : ''}`}
                title={st.name_fa || labelState(st.code)}
              >
                <span className="quest-step-num">{i + 1}</span>
                <span className="quest-step-label">{st.name_fa || labelState(st.code)}</span>
              </div>
            )
          })}
        </div>
      )}

      <div className="quest-current-box">
        <span className="quest-current-label">وضعیت فعلی</span>
        <strong className="quest-current-value">{currentStateLabel}</strong>
      </div>

      {!done && studentForms.length > 0 && stepFormLocked && (
        <div className="quest-forms-wrap">
          <div className="psf-locked-banner" role="status" style={{
            padding: '1rem 1.25rem', borderRadius: '10px',
            background: 'linear-gradient(135deg, #ecfdf5 0%, #f0fdf4 100%)',
            borderRight: '4px solid #16a34a', fontSize: '0.9rem', lineHeight: 1.7,
          }}>
            اطلاعات این مرحله قبلاً ثبت شده است. برای ویرایش، مسئول مربوط (اداری) باید از پنل کارمندان، امکان ویرایش را برای شما باز کند؛ سپس همین صفحه را تازه کنید.
          </div>
        </div>
      )}
      {!done && studentForms.length > 0 && !stepFormLocked && (
        <div className="quest-forms-wrap">
          <ProcessStepForms
            forms={forms}
            values={stepFormValues || {}}
            onFieldChange={onStepFieldChange}
            disabled={false}
            hasAvailableTransitions={(transitions?.length || 0) > 0}
            onRegisterSubmit={onFormRegisterSubmit}
          />
        </div>
      )}

      {!done && transitions?.length > 0 && (
        <div className="quest-actions">
          <p className="quest-actions-title">قدم بعد (فقط اقدامات مجاز برای شما در این مرحله)</p>
          {transitionBlocked && (
            <p className="quest-block-hint">
              ابتدا فرم بالا را تکمیل کنید؛ سپس دکمهٔ مرحلهٔ بعد فعال می‌شود.
            </p>
          )}
          <p style={{ fontSize: '0.78rem', opacity: 0.88, marginBottom: '0.45rem', fontWeight: 600 }}>
            توضیح همراه اقدام (اختیاری)
          </p>
          <textarea
            value={decisionNotes}
            onChange={e => onDecisionNotesChange(e.target.value)}
            placeholder="در صورت نیاز توضیح کوتاه بنویسید — با همان دکمه ثبت می‌شود."
            className="quest-payload"
            dir="rtl"
          />
          <div className="quest-btn-row">
            {transitions.map((t, idx) => (
              <button
                key={`${t.trigger_event}-${idx}`}
                type="button"
                data-testid={`quest-transition-${t.to_state || t.trigger_event || idx}`}
                className="btn quest-cta"
                disabled={transitionBlocked}
                onClick={() => onTrigger(t)}
                title={transitionBlocked ? 'فرم این مرحله را کامل کنید' : (t.description || t.description_fa || t.trigger_event)}
              >
                <span className="quest-cta-main">{t.description_fa || t.description || t.trigger_event}</span>
                {t.to_state && (
                  <span className="quest-cta-sub">→ {labelState(t.to_state)}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="quest-footer">
        <button type="button" className="btn btn-outline btn-sm" onClick={onOpenProcesses}>
          جزئیات کامل در «فرایندها»
        </button>
      </div>
    </div>
  )
}
