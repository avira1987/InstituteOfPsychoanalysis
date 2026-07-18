import InstituteAcademicCalendarPanel from './InstituteAcademicCalendarPanel'

/**
 * کارت فشردهٔ تقویم آموزشی در پورتال دانشجو — با لینک به صفحهٔ کامل.
 */
export default function StudentAcademicCalendarPanel({ onOpenProcesses }) {
  return (
    <InstituteAcademicCalendarPanel
      variant="compact"
      showFullPageLink
      onOpenProcesses={onOpenProcesses}
      testId="student-academic-calendar-panel"
      embedded
    />
  )
}
