import { Navigate } from 'react-router-dom'

/** سازگاری با لینک قدیمی — هدایت به workbench یکپارچه */
export default function SemesterPrepCalendarPage() {
  return <Navigate to="/panel/semester-prep/workbench?process_code=fall_semester_preparation" replace />
}
