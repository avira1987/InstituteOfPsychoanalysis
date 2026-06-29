import React, { useMemo } from 'react'
import { labelState } from '../utils/processDisplay'
import UploadedDocumentsReadonlyGrid from './UploadedDocumentsReadonlyGrid'
import {
  TaEssayFlowStepper,
  TaEssaySlaBanner,
  SessionInfoTiles,
  HintBlock,
  TA_ESSAY_TEMPLATE_PATH,
  resolveSessionContext,
  resolveEssayFiles,
  resolveInstructorRejection,
  resolvePublicationPlatforms,
  fmtIsoDate,
  fileUploadLabel,
} from '../utils/taEssayUploadDisplay'

const PROCESS_TITLE_FA = 'آپلود جستار هر جلسه و دقایق منتخب فیلم کلاس (فرایند ۴۵)'

const REF_CENTER_INSTRUCTION_FA =
  'نسبت به فایل اقدامات زیر انجام شود: ۱) ویرایش ادبی متن جستار ۲) دقیقهٔ مهم منتخب کمک‌مدرس را در نظر گرفته و بازهٔ دقایق مهم این مطلب را با مشاهدهٔ فیلم ضبط‌شدهٔ کلاس دقیق‌تر استخراج و در فرم ثبت کنید.'

function roleBucket(portalRole) {
  const r = (portalRole || '').toLowerCase()
  if (r === 'teaching_assistant') return 'ta'
  if (r === 'instructor') return 'instructor'
  if (r === 'reference_center') return 'reference_center'
  if (r === 'marketing' || r === 'admissions_officer') return 'marketing'
  if (r === 'admin' || r === 'staff') return 'admin'
  return 'other'
}

const ESSAY_FILE_FIELDS = [
  { name: 'essay_word', label_fa: 'فایل Word', type: 'file_upload' },
  { name: 'essay_pdf', label_fa: 'فایل PDF', type: 'file_upload' },
]

const EDITED_FILE_FIELDS = [
  { name: 'edited_essay_word', label_fa: 'فایل Word نهایی (مرکز مرجع)', type: 'file_upload' },
]

/**
 * داشبورد راهنمای فرایند ۴۵ — آپلود جستار و دقایق منتخب.
 */
export default function TaEssayUploadPanel({
  detail = null,
  active = true,
  portalRole = 'staff',
  compact = false,
}) {
  const ctx = detail?.context_data || {}
  const currentState = detail?.current_state || null
  const bucket = roleBucket(portalRole)

  const session = useMemo(() => resolveSessionContext(ctx), [ctx])
  const files = useMemo(() => resolveEssayFiles(ctx), [ctx])
  const rejectionNote = useMemo(() => resolveInstructorRejection(ctx), [ctx])
  const publications = useMemo(() => resolvePublicationPlatforms(ctx), [ctx])

  if (!active || !detail || detail.process_code !== 'ta_essay_upload') {
    return null
  }

  const showTaUploadHints = currentState === 'ta_upload' && (bucket === 'ta' || bucket === 'admin')
  const showRevisionHints = currentState === 'rejected_revision' && (bucket === 'ta' || bucket === 'admin')
  const showInstructorHints = currentState === 'instructor_review' && (bucket === 'instructor' || bucket === 'admin')
  const showRefCenterHints = currentState === 'reference_center_editing'
    && (bucket === 'reference_center' || bucket === 'admin')
  const showMarketingHints = currentState === 'marketing_publication'
    && (bucket === 'marketing' || bucket === 'admin')
  const showPublishedSummary = currentState === 'content_published'

  const showEssayPreview = ['instructor_review', 'reference_center_editing', 'marketing_publication', 'content_published']
    .includes(currentState)

  return (
    <div
      data-testid="ta-essay-upload-panel"
      style={{
        padding: compact ? '0.75rem' : '1rem 1.25rem',
        marginBottom: '1.25rem',
        background: '#f0fdfa',
        borderRadius: '10px',
        borderRight: '4px solid #0d9488',
      }}
    >
      <h4 style={{ fontSize: '0.9rem', fontWeight: 700, margin: '0 0 0.35rem', color: '#115e59' }}>
        {PROCESS_TITLE_FA}
      </h4>
      {!compact && (
        <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 0.75rem' }}>
          وضعیت:
          {' '}
          <strong>{labelState(currentState)}</strong>
        </p>
      )}

      <TaEssayFlowStepper currentState={currentState} />
      <SessionInfoTiles session={session} />

      <TaEssaySlaBanner
        ctx={ctx}
        currentState={currentState}
        startedAt={detail.started_at}
      />

      {showTaUploadHints && (
        <>
          <HintBlock tone="info">
            قالب خام را
            {' '}
            <a href={TA_ESSAY_TEMPLATE_PATH} download style={{ fontWeight: 600 }}>
              دانلود کنید
            </a>
            ؛ جستار و دقایق منتخب را در Word بنویسید و هر دو فایل Word و PDF را در فرم زیر آپلود کنید.
            پس از «ثبت فرم»، دکمه «ثبت آپلود و ارسال به مدرس» را بزنید.
          </HintBlock>
        </>
      )}

      {showRevisionHints && (
        <>
          {rejectionNote && (
            <div
              data-testid="ta-essay-rejection-feedback"
              style={{
                marginBottom: '0.85rem',
                padding: '0.75rem 1rem',
                borderRadius: '8px',
                background: '#fef2f2',
                border: '1px solid #fecaca',
                fontSize: '0.85rem',
                lineHeight: 1.7,
                color: '#991b1b',
              }}
            >
              <strong>بازخورد مدرس:</strong>
              <div style={{ marginTop: '0.35rem' }}>{rejectionNote}</div>
            </div>
          )}
          <HintBlock tone="warn">
            فایل‌ها را مطابق بازخورد مدرس اصلاح کنید و مجدداً Word و PDF را آپلود کنید؛ سپس «اصلاح و ارسال مجدد» را بزنید.
          </HintBlock>
        </>
      )}

      {showInstructorHints && (
        <HintBlock tone="info">
          فایل‌های آپلودشده را بررسی کنید. در صورت «غیر قابل قبول»، حتماً توضیح رد را در بخش «توضیح یا نظر» بنویسید.
        </HintBlock>
      )}

      {showRefCenterHints && (
        <>
          <HintBlock tone="info">{REF_CENTER_INSTRUCTION_FA}</HintBlock>
          <UploadedDocumentsReadonlyGrid fields={ESSAY_FILE_FIELDS} contextData={ctx} />
          {files.minutesNote && (
            <p style={{ fontSize: '0.82rem', margin: '0 0 0.75rem', color: '#334155' }}>
              <strong>یادداشت دقایق TA:</strong>
              {' '}
              {files.minutesNote}
            </p>
          )}
        </>
      )}

      {showMarketingHints && (
        <>
          <HintBlock tone="warn">
            این محتوا در بخش «تعیین‌تکلیف‌نشده» است. پلتفرم‌های انتشار را انتخاب کنید و برای هر مورد تاریخ انتشار را ثبت کنید.
            مهلت ۷ روز — پس از آن فقط هشدار به معاون آموزش ارسال می‌شود.
          </HintBlock>
          <UploadedDocumentsReadonlyGrid
            fields={files.editedWord ? EDITED_FILE_FIELDS : ESSAY_FILE_FIELDS}
            contextData={ctx}
          />
          {files.refinedMinutes && (
            <p style={{ fontSize: '0.82rem', margin: '0 0 0.75rem', color: '#334155' }}>
              <strong>بازهٔ دقایق (مرکز مرجع):</strong>
              {' '}
              {files.refinedMinutes}
            </p>
          )}
        </>
      )}

      {showEssayPreview && !showRefCenterHints && !showMarketingHints && (
        <div style={{ marginBottom: '0.85rem' }}>
          <div style={{ fontSize: '0.8rem', fontWeight: 600, marginBottom: '0.4rem', color: '#334155' }}>
            فایل‌های آپلودشده
          </div>
          <UploadedDocumentsReadonlyGrid fields={ESSAY_FILE_FIELDS} contextData={ctx} />
          {files.minutesNote && (
            <p style={{ fontSize: '0.82rem', marginTop: '0.5rem', color: '#64748b' }}>
              یادداشت دقایق:
              {' '}
              {files.minutesNote}
            </p>
          )}
        </div>
      )}

      {showPublishedSummary && (
        <div data-testid="ta-essay-publication-summary">
          <HintBlock tone="success">فرایند با موفقیت به پایان رسید. خلاصهٔ انتشار:</HintBlock>
          {publications.length > 0 ? (
            <ul style={{ margin: 0, paddingRight: '1.2rem', fontSize: '0.85rem', lineHeight: 1.8 }}>
              {publications.map((p) => (
                <li key={p.code}>
                  {p.label}
                  {' '}
                  —
                  {' '}
                  {p.publishDate ? fmtIsoDate(p.publishDate) : 'تاریخ ثبت نشده'}
                </li>
              ))}
            </ul>
          ) : (
            <p style={{ fontSize: '0.82rem', color: '#64748b', margin: 0 }}>
              Word:
              {' '}
              {fileUploadLabel(files.editedWord || files.word)}
              {' '}
              | PDF:
              {' '}
              {fileUploadLabel(files.pdf)}
            </p>
          )}
        </div>
      )}
    </div>
  )
}
