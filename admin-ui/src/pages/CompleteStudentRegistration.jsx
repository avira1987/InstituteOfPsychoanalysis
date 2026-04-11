import React from 'react'
import StudentRegistration from './public/StudentRegistration'

/** تکمیل ثبت‌نام پس از ورود با OTP — همان فرم عمومی با mode=panel */
export default function CompleteStudentRegistration() {
  return (
    <div className="page-content" style={{ maxWidth: 920, margin: '0 auto', padding: '0.5rem 0 2rem' }}>
      <StudentRegistration mode="panel" />
    </div>
  )
}
