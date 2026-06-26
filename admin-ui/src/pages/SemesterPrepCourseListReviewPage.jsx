import { Navigate } from 'react-router-dom'

/** سازگاری با لینک قدیمی — هدایت به workbench یکپارچه */
export default function SemesterPrepCourseListReviewPage() {
  return <Navigate to="/panel/semester-prep/workbench?process_code=winter_semester_preparation" replace />
}
