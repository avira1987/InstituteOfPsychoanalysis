"""Validation and serialization for extended student registration profile (student.extra_data)."""

import re
from typing import Any, Literal, Optional, Union

from fastapi import HTTPException
from pydantic import BaseModel, Field

YesNo = Literal["yes", "no"]
ParticipationMode = Literal["in_person", "online"]
ReferralSource = Literal[
    "person_referral",
    "website",
    "social_media",
    "search",
    "other",
]

REGISTRATION_PROFILE_EXTRA_KEYS = (
    "first_name_fa",
    "last_name_fa",
    "age",
    "birth_certificate_number",
    "birth_date",
    "residence_city",
    "home_address",
    "work_address",
    "home_phone",
    "work_phone",
    "had_psychotherapy",
    "used_psychiatric_meds",
    "psychiatric_hospitalization_history",
    "has_work_permit",
    "has_university_degree",
    "course_participation_mode",
    "referral_source",
    "referral_inviter_name",
)

_REQUIRED_ON_REGISTER = (
    "first_name_fa",
    "last_name_fa",
    "age",
    "birth_certificate_number",
    "birth_date",
    "residence_city",
    "home_address",
    "work_address",
    "home_phone",
    "work_phone",
    "had_psychotherapy",
    "used_psychiatric_meds",
    "psychiatric_hospitalization_history",
    "has_work_permit",
    "has_university_degree",
    "course_participation_mode",
    "referral_source",
)

_BIRTH_DATE_RE = re.compile(r"^\d{4}/\d{2}/\d{2}$")
_PHONE_LANDLINE_RE = re.compile(r"^0\d{10,11}$")


class StudentRegistrationProfileFields(BaseModel):
    first_name_fa: Optional[str] = None
    last_name_fa: Optional[str] = None
    age: Optional[int] = Field(default=None, ge=6, le=120)
    birth_certificate_number: Optional[str] = None
    birth_date: Optional[str] = None
    residence_city: Optional[str] = None
    home_address: Optional[str] = None
    work_address: Optional[str] = None
    home_phone: Optional[str] = None
    work_phone: Optional[str] = None
    had_psychotherapy: Optional[YesNo] = None
    used_psychiatric_meds: Optional[YesNo] = None
    psychiatric_hospitalization_history: Optional[YesNo] = None
    has_work_permit: Optional[YesNo] = None
    has_university_degree: Optional[YesNo] = None
    course_participation_mode: Optional[ParticipationMode] = None
    referral_source: Optional[ReferralSource] = None
    referral_inviter_name: Optional[str] = None


def _as_model(data: Union[StudentRegistrationProfileFields, BaseModel, dict]) -> StudentRegistrationProfileFields:
    if isinstance(data, StudentRegistrationProfileFields):
        return data
    if isinstance(data, BaseModel):
        return StudentRegistrationProfileFields.model_validate(data.model_dump(exclude_unset=True))
    return StudentRegistrationProfileFields.model_validate(data)


def _strip_str(val: Any) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _validate_landline(raw: str, label: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if not digits.startswith("0"):
        digits = "0" + digits if digits else ""
    if not _PHONE_LANDLINE_RE.match(digits):
        raise HTTPException(
            status_code=400,
            detail=f"{label} را با پیش‌شمارهٔ شهر وارد کنید (مثال: ۰۲۱۱۲۳۴۵۶۷۸).",
        )
    return digits


def validate_registration_profile_fields(
    data: Union[StudentRegistrationProfileFields, BaseModel, dict],
    *,
    require_all: bool = True,
) -> dict:
    """
    اعتبارسنجی فیلدهای تکمیلی؛ برای ثبت‌نام require_all=True، برای PATCH ادمین False.
    فقط کلیدهای پر شده در extra_data ذخیره می‌شوند.
    """
    model = _as_model(data)
    raw = model.model_dump()

    if require_all:
        for key in _REQUIRED_ON_REGISTER:
            val = raw.get(key)
            if val is None or (isinstance(val, str) and not str(val).strip()):
                raise HTTPException(status_code=400, detail=_missing_message(key))

    out: dict = {}

    fn = _strip_str(raw.get("first_name_fa"))
    ln = _strip_str(raw.get("last_name_fa"))
    if fn:
        out["first_name_fa"] = fn
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("first_name_fa"))
    if ln:
        out["last_name_fa"] = ln
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("last_name_fa"))

    age = raw.get("age")
    if age is not None:
        try:
            age_i = int(age)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="سن را به‌صورت عدد بین ۶ تا ۱۲۰ وارد کنید.")
        if age_i < 6 or age_i > 120:
            raise HTTPException(status_code=400, detail="لطفاً یک عدد مابین ۶ تا ۱۲۰ وارد کنید.")
        out["age"] = age_i
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("age"))

    bc = _strip_str(raw.get("birth_certificate_number"))
    if bc:
        out["birth_certificate_number"] = bc
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("birth_certificate_number"))

    bd = _strip_str(raw.get("birth_date"))
    if bd:
        if not _BIRTH_DATE_RE.match(bd):
            raise HTTPException(
                status_code=400,
                detail="تاریخ تولد را به فرمت شمسی وارد کنید (مثال: ۱۳۷۰/۰۱/۱۵).",
            )
        out["birth_date"] = bd
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("birth_date"))

    for text_key in ("residence_city", "home_address", "work_address"):
        val = _strip_str(raw.get(text_key))
        if val:
            out[text_key] = val
        elif require_all:
            raise HTTPException(status_code=400, detail=_missing_message(text_key))

    for phone_key, label in (("home_phone", "تلفن منزل"), ("work_phone", "تلفن محل کار")):
        raw_phone = _strip_str(raw.get(phone_key))
        if raw_phone:
            out[phone_key] = _validate_landline(raw_phone, label)
        elif require_all:
            raise HTTPException(status_code=400, detail=_missing_message(phone_key))

    for yn_key in (
        "had_psychotherapy",
        "used_psychiatric_meds",
        "psychiatric_hospitalization_history",
        "has_work_permit",
        "has_university_degree",
    ):
        val = raw.get(yn_key)
        if val in ("yes", "no"):
            out[yn_key] = val
        elif require_all:
            raise HTTPException(status_code=400, detail=_missing_message(yn_key))

    mode = raw.get("course_participation_mode")
    if mode in ("in_person", "online"):
        out["course_participation_mode"] = mode
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("course_participation_mode"))

    ref = raw.get("referral_source")
    allowed_ref = {"person_referral", "website", "social_media", "search", "other"}
    if ref in allowed_ref:
        out["referral_source"] = ref
    elif require_all:
        raise HTTPException(status_code=400, detail=_missing_message("referral_source"))

    inviter = _strip_str(raw.get("referral_inviter_name"))
    if ref == "person_referral":
        if not inviter:
            raise HTTPException(
                status_code=400,
                detail="نام شخص معرف را وارد کنید.",
            )
        out["referral_inviter_name"] = inviter
    elif inviter:
        out["referral_inviter_name"] = inviter

    return out


def registration_profile_from_extra(extra: dict) -> dict:
    """خواندن فیلدهای تکمیلی از extra_data برای API و UI."""
    if not extra:
        extra = {}
    result = {}
    for key in REGISTRATION_PROFILE_EXTRA_KEYS:
        if key in extra and extra[key] is not None:
            result[key] = extra[key]
    return result


def _missing_message(key: str) -> str:
    labels = {
        "first_name_fa": "نام",
        "last_name_fa": "نام خانوادگی",
        "age": "سن",
        "birth_certificate_number": "شماره شناسنامه",
        "birth_date": "تاریخ تولد",
        "residence_city": "شهر محل سکونت",
        "home_address": "آدرس منزل",
        "work_address": "آدرس محل کار",
        "home_phone": "تلفن منزل",
        "work_phone": "تلفن محل کار",
        "had_psychotherapy": "تجربه درمان روان‌شناختی",
        "used_psychiatric_meds": "استفاده از داروهای اعصاب و روان",
        "psychiatric_hospitalization_history": "سابقه بستری روانپزشکی",
        "has_work_permit": "پروانه اشتغال",
        "has_university_degree": "مدرک دانشگاهی",
        "course_participation_mode": "نحوه شرکت در دوره",
        "referral_source": "نحوه آشنایی با انستیتو",
        "referral_inviter_name": "نام شخص معرف",
    }
    label = labels.get(key, key)
    return f"{label} را وارد کنید."
