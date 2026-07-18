import React from 'react'
import InstituteAcademicCalendarPanel from '../components/InstituteAcademicCalendarPanel'

export default function AcademicCalendarPage() {
  return (
    <div data-testid="institute-academic-calendar-page">
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h1 className="page-title" style={{ margin: 0 }}>
          تقویم آموزشی انستیتو
        </h1>
        <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.9rem', lineHeight: 1.65 }}>
          تاریخ‌های رسمی ترم پاییز و زمستان، مهلت ثبت‌نام، تعطیلات و مهلت‌های مهم انستیتو.
        </p>
      </div>
      <InstituteAcademicCalendarPanel
        variant="full"
        embedded
        showPrepDetailsLink
        testId="institute-academic-calendar-page-panel"
      />
    </div>
  )
}
