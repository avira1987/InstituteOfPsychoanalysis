import React from 'react'
import { useToast } from '../contexts/ToastContext'
import CourseCommitteeRosterPanel from '../components/CourseCommitteeRosterPanel'

/** صفحه مستقل مدیریت چارت کمیته دروس — مسیر /panel/course-committee-roster */
export default function CourseCommitteeRosterPage() {
  const { showToast } = useToast()
  return (
    <div className="page-content" style={{ maxWidth: 960, margin: '0 auto' }}>
      <h2 style={{ marginBottom: '0.5rem' }}>مدیریت چارت کمیته دروس</h2>
      <CourseCommitteeRosterPanel showToast={showToast} embedded={false} />
    </div>
  )
}
