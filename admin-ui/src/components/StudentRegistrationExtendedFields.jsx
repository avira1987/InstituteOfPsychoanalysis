import React from 'react'
import { REGISTRATION_FIELD_LABELS } from '../utils/studentRegistrationProfile'

function YesNoRadios({ name, label, value, onChange, required }) {
  return (
    <div className="pub-form-group pub-form-group-full">
      <label>
        {label}
        {required ? ' *' : ''}
      </label>
      <div className="pub-radio-row">
        <label className="pub-radio-label">
          <input
            type="radio"
            name={name}
            value="yes"
            checked={value === 'yes'}
            onChange={onChange}
            required={required}
          />
          بله
        </label>
        <label className="pub-radio-label">
          <input
            type="radio"
            name={name}
            value="no"
            checked={value === 'no'}
            onChange={onChange}
            required={required}
          />
          خیر
        </label>
      </div>
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <h3 style={{ margin: '1.25rem 0 0.75rem', fontSize: '1.05rem', fontWeight: 600 }}>
      {children}
    </h3>
  )
}

/**
 * @param {{ form: Record<string, string>, onChange: (e: React.ChangeEvent) => void, className?: string }} props
 */
export default function StudentRegistrationExtendedFields({ form, onChange, className = '' }) {
  return (
    <div className={className || undefined} data-testid="registration-extended-fields">
      <SectionTitle>اطلاعات شخصی تکمیلی</SectionTitle>

      <div className="pub-form-row">
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.first_name_fa} *</label>
          <input
            data-testid="register-input-first_name_fa"
            name="first_name_fa"
            value={form.first_name_fa || ''}
            onChange={onChange}
            required
          />
        </div>
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.last_name_fa} *</label>
          <input
            name="last_name_fa"
            value={form.last_name_fa || ''}
            onChange={onChange}
            required
          />
        </div>
      </div>

      <div className="pub-form-row">
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.age} *</label>
          <input
            name="age"
            value={form.age || ''}
            onChange={onChange}
            inputMode="numeric"
            placeholder="مثلاً ۳۵"
            required
          />
          <span style={{ fontSize: '0.78rem', color: 'var(--text-light)' }}>
            لطفاً یک عدد مابین ۶ تا ۱۲۰ وارد کنید.
          </span>
        </div>
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.birth_certificate_number} *</label>
          <input
            name="birth_certificate_number"
            value={form.birth_certificate_number || ''}
            onChange={onChange}
            required
          />
        </div>
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.birth_date} *</label>
          <input
            name="birth_date"
            value={form.birth_date || ''}
            onChange={onChange}
            placeholder="۱۳۷۰/۰۱/۱۵"
            required
            style={{ direction: 'ltr', textAlign: 'right' }}
          />
        </div>
      </div>

      <div className="pub-form-group pub-form-group-full">
        <label>{REGISTRATION_FIELD_LABELS.residence_city} *</label>
        <input
          name="residence_city"
          value={form.residence_city || ''}
          onChange={onChange}
          placeholder="ساکن کدام شهر هستید؟"
          required
        />
      </div>

      <div className="pub-form-group pub-form-group-full">
        <label>{REGISTRATION_FIELD_LABELS.home_address} *</label>
        <input
          name="home_address"
          value={form.home_address || ''}
          onChange={onChange}
          required
        />
      </div>

      <div className="pub-form-group pub-form-group-full">
        <label>{REGISTRATION_FIELD_LABELS.work_address} *</label>
        <input
          name="work_address"
          value={form.work_address || ''}
          onChange={onChange}
          required
        />
      </div>

      <div className="pub-form-row">
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.home_phone} *</label>
          <input
            name="home_phone"
            value={form.home_phone || ''}
            onChange={onChange}
            placeholder="02100000000"
            required
            style={{ direction: 'ltr', textAlign: 'right' }}
          />
        </div>
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.work_phone} *</label>
          <input
            name="work_phone"
            value={form.work_phone || ''}
            onChange={onChange}
            placeholder="02100000000"
            required
            style={{ direction: 'ltr', textAlign: 'right' }}
          />
        </div>
      </div>

      <SectionTitle>تجربیات شخصی</SectionTitle>

      <YesNoRadios
        name="had_psychotherapy"
        label="آیا تا به حال تجربه درمان روان‌شناختی داشته‌اید؟"
        value={form.had_psychotherapy}
        onChange={onChange}
        required
      />
      <YesNoRadios
        name="used_psychiatric_meds"
        label="آیا تا به حال از داروهای اعصاب و روان استفاده کرده‌اید؟"
        value={form.used_psychiatric_meds}
        onChange={onChange}
        required
      />
      <YesNoRadios
        name="psychiatric_hospitalization_history"
        label="آیا تا به حال سابقه بستری در بیمارستان‌های روانپزشکی داشته‌اید؟"
        value={form.psychiatric_hospitalization_history}
        onChange={onChange}
        required
      />

      <SectionTitle>اطلاعات حرفه‌ای و دوره</SectionTitle>

      <YesNoRadios
        name="has_work_permit"
        label="آیا دارای پروانه اشتغال به کار هستید؟"
        value={form.has_work_permit}
        onChange={onChange}
        required
      />
      <YesNoRadios
        name="has_university_degree"
        label="آیا مدرک دانشگاهی دارید؟"
        value={form.has_university_degree}
        onChange={onChange}
        required
      />

      <div className="pub-form-group pub-form-group-full">
        <label>{REGISTRATION_FIELD_LABELS.course_participation_mode} *</label>
        <div className="pub-radio-row">
          <label className="pub-radio-label">
            <input
              type="radio"
              name="course_participation_mode"
              value="in_person"
              checked={form.course_participation_mode === 'in_person'}
              onChange={onChange}
              required
            />
            حضوری
          </label>
          <label className="pub-radio-label">
            <input
              type="radio"
              name="course_participation_mode"
              value="online"
              checked={form.course_participation_mode === 'online'}
              onChange={onChange}
              required
            />
            آنلاین
          </label>
        </div>
      </div>

      <div className="pub-form-row">
        <div className="pub-form-group">
          <label>{REGISTRATION_FIELD_LABELS.referral_source} *</label>
          <select
            name="referral_source"
            value={form.referral_source || ''}
            onChange={onChange}
            required
          >
            <option value="">انتخاب کنید</option>
            <option value="person_referral">معرفی شخص</option>
            <option value="website">وب‌سایت</option>
            <option value="social_media">شبکه‌های اجتماعی</option>
            <option value="search">جستجو در اینترنت</option>
            <option value="other">سایر</option>
          </select>
        </div>
        {form.referral_source === 'person_referral' && (
          <div className="pub-form-group">
            <label>{REGISTRATION_FIELD_LABELS.referral_inviter_name} *</label>
            <input
              name="referral_inviter_name"
              value={form.referral_inviter_name || ''}
              onChange={onChange}
              placeholder="نام شخص دعوت‌کننده"
              required
            />
          </div>
        )}
      </div>
    </div>
  )
}
