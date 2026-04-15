"""Notification Service - SMS, Email, and alert delivery (with placeholders for external APIs)."""

import logging
from typing import Optional
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    IN_APP = "in_app"
    PUSH = "push"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"


class NotificationResult:
    """Result of a notification send attempt."""
    def __init__(self, success: bool, notification_type: str,
                 recipient: str, message: str = "", error: str = ""):
        self.success = success
        self.notification_type = notification_type
        self.recipient = recipient
        self.message = message
        self.error = error
        self.timestamp = datetime.now(timezone.utc)

    def to_dict(self):
        return {
            "success": self.success,
            "type": self.notification_type,
            "recipient": self.recipient,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# ─── Notification Templates ────────────────────────────────────

TEMPLATES = {
    "leave_approved": {
        "sms": "دانشجوی گرامی، درخواست مرخصی آموزشی شما تایید شد.",
        "email_subject": "تایید مرخصی آموزشی",
        "email_body": "با سلام، درخواست مرخصی آموزشی شما مورد تایید کمیته پیشرفت قرار گرفت.",
    },
    "leave_rejected": {
        "sms": "دانشجوی گرامی، درخواست مرخصی آموزشی شما رد شد. لطفاً با دفتر تماس بگیرید.",
        "email_subject": "رد درخواست مرخصی آموزشی",
        "email_body": "با سلام، متأسفانه درخواست مرخصی آموزشی شما رد شد.",
    },
    "leave_approved_intern_1": {
        "sms": "دانشجوی انترن گرامی، مرخصی ۱ ترمی شما تایید شد.",
    },
    "leave_approved_intern_2_warning": {
        "sms": "هشدار: با تایید وقفه ۲ ترمی، وضعیت انترنی شما لغو خواهد شد.",
    },
    "return_reminder": {
        "sms": "یادآوری: مهلت بازگشت از مرخصی آموزشی شما نزدیک است. لطفاً اقدام فرمایید.",
    },
    "violation_no_return": {
        "sms": "اخطار: عدم بازگشت از مرخصی آموزشی. تخلف ثبت شد.",
    },
    "therapy_eligible": {
        "sms": "دانشجوی گرامی، شما واجد شرایط شروع درمان آموزشی هستید.",
    },
    "therapy_ineligible": {
        "sms": "متأسفانه شرایط شروع درمان آموزشی فراهم نیست.",
    },
    "week9_block": {
        "sms": "اخطار: مهلت هفته نهم آغاز درمان آموزشی تمام شده و دسترسی کلاس مسدود شد.",
    },
    "therapy_started": {
        "sms": "درمان آموزشی شما آغاز شد. اولین جلسه برنامه‌ریزی شده است.",
    },
    "therapist_declined": {
        "sms": "درمانگر انتخابی پذیرفته نشد. لطفاً درمانگر دیگری انتخاب کنید.",
    },
    "therapy_restart_approved": {
        "sms": "درخواست آغاز مجدد درمان شما تایید شد.",
    },
    "change_rejected": {
        "sms": "درخواست تغییر درمان شما رد شد.",
    },
    "therapist_changed": {
        "sms": "درمانگر شما با موفقیت تغییر یافت.",
    },
    "schedule_changed": {
        "sms": "ساعت جلسات درمان با موفقیت تغییر یافت.",
    },
    "extra_session_request": {
        "sms": "درخواست جلسه اضافی از سوی دانشجو ثبت شده. لطفاً بررسی فرمایید.",
    },
    "extra_session_confirmed": {
        "sms": "جلسه اضافی درمان تایید و برنامه‌ریزی شد.",
    },
    "extra_supervision_request": {
        "sms": "درخواست جلسه اضافی سوپرویژن از سوی دانشجو ثبت شده. لطفاً در پورتال بررسی فرمایید."
    },
    "extra_supervision_approved": {
        "in_app": "سوپروایزر زمان پیشنهادی را تایید کرد. لطفاً جهت پرداخت جلسه اضافی اقدام کنید."
    },
    "extra_supervision_alternative_proposed": {
        "in_app": "سوپروایزر زمان دیگری پیشنهاد داده. لطفا تاریخ و ساعت پیشنهادی خود را در توضیحات ببینید و زمان جدید را وارد کنید."
    },
    "extra_supervision_confirmed": {
        "sms": "جلسه اضافی سوپرویژن: روز {day} ساعت {time} تاریخ {date}. انستیتو روانکاوی تهران."
    },
    "extra_supervision_rejected": {
        "sms": "دانشجوی گرامی، پیرو درخواست شما برای برگزاری جلسه اضافی سوپروژن فردی، متاسفانه سوپروایزر شما اعلام کرده است که امکان برگزاری جلسه اضافی را ندارد.",
        "in_app": "امکان برگزاری جلسه اضافه را ندارم. (نظر سوپروایزر)"
    },
    "extra_session_rejected": {
        "sms": "درخواست جلسه اضافی رد شد. درمانگر امکان برگزاری جلسه اضافه را ندارد.",
    },
    "extra_session_approved_payment": {
        "sms": "درخواست جلسه اضافی شما تایید شد. لطفاً برای پرداخت به پورتال مراجعه کنید.",
    },
    "extra_session_alternative_proposed": {
        "sms": "درمانگر زمان پیشنهادی دیگری دارد. لطفاً به پورتال مراجعه کرده و تاریخ و ساعت را تایید یا اصلاح کنید.",
    },
    "extra_session_cancelled": {
        "sms": "جلسه اضافی لغو شد.",
    },
    "extra_session_payment_timeout": {
        "sms": "مهلت پرداخت جلسه اضافی تمام شد. جلسه لغو شد.",
    },
    "extra_session_sla_therapist": {
        "sms": "یادآوری: درخواست جلسه اضافی درمان در کارتابل شماست؛ لطفاً در پورتال بررسی کنید.",
    },
    "extra_session_sla_payment": {
        "sms": "یادآوری: برای جلسه اضافی درمان، پرداخت را در پورتال دانشجویی تکمیل کنید.",
    },
    "payment_invoice": {
        "sms": "فاکتور پرداخت جلسه درمان صادر شد. لطفاً پرداخت کنید.",
    },
    "payment_confirmed": {
        "sms": "پرداخت شما تایید شد. جلسات فعال است.",
    },
    "payment_overdue": {
        "sms": "پرداخت شما عقب افتاده. لطفاً هرچه زودتر اقدام کنید.",
    },
    "payment_rejected": {
        "sms": "پرداخت شما تایید نشد. لطفاً مجدداً تلاش کنید.",
    },
    "payment_retry": {
        "sms": "لطفاً پرداخت را مجدداً انجام دهید.",
    },
    "session_payment_sla_payment": {
        "sms": "یادآوری: مهلت پرداخت جلسات درمان در پورتال رو به پایان است؛ لطفاً هرچه زودتر از بخش پرداخت اقدام کنید.",
    },
    "debt_settlement_required": {
        "sms": "دانشجوی گرامی، به دلیل وجود بدهی، لطفاً تسویه بدهی را همراه با جلسات آتی انتخاب کنید.",
    },
    "sessions_suspended": {
        "sms": "جلسات درمان به دلیل عدم پرداخت معلق شد.",
    },
    "session_reminder": {
        "sms": "یادآوری: جلسه درمان آموزشی شما در ساعت آینده برگزار می‌شود.",
    },
    "attendance_followup_required": {
        "sms": "وضعیت جلسه درمان آموزشی نامشخص است. لطفاً از درمانگر پیگیری فرمایید.",
        "in_app": "وضعیت جلسه مورخ {session_date} درمانگر آموزشی {therapist_name} با دانشجو {student_name} نامشخص است. لطفاً از درمانگر آموزشی پیگیری بفرمایید.",
    },
    "attendance_site_manager_delay": {
        "sms": "مسئول سایت در پیگیری وضعیت جلسه درمان آموزشی بدون ثبت حضور یا غیاب اهمال کرده است.",
    },
    "absence_recorded": {
        "sms": "غیبت غیرموجه شما ثبت و هزینه محاسبه شد.",
    },
    "quota_exceeded": {
        "sms": "اخطار: سهمیه غیبت مجاز سالانه شما تمام شده است.",
    },
    "therapy_completed": {
        "sms": "تبریک! ساعات درمان آموزشی شما تکمیل شد.",
    },
    "therapy_completion_conditions_not_met": {
        "sms": "شرایط خاتمه درمان هنوز کامل نیست. جزئیات ساعات در پورتال بخش همین فرایند را ببینید.",
        "in_app": "شرایط خاتمه احراز نشده است. وضعیت فعلی: درمان {therapy_hours}/{therapy_threshold}، بالینی {clinical_hours}/{clinical_threshold}، سوپرویژن {supervision_hours}/{supervision_threshold}.",
    },
    "therapy_completion_success": {
        "sms": "درمان آموزشی با موفقیت تکمیل و خاتمه یافت.",
        "in_app": "درمان آموزشی با موفقیت تکمیل و خاتمه یافت.",
    },
    "therapy_session_increase_request": {
        "sms": "درخواست دانشجو برای افزایش جلسات هفتگی درمان آموزشی ثبت شده. لطفاً در پورتال بررسی فرمایید.",
    },
    "therapy_session_increase_approved": {
        "in_app": "درخواست افزایش جلسه تایید شد. روز و ساعت جدید به برنامه درمان آموزشی شما اضافه شد.",
    },
    "therapy_session_increase_alternative": {
        "sms": "درمانگر آموزشی زمان پیشنهادی دیگری دارد. لطفاً به پورتال مراجعه کرده و روز و ساعت را تایید یا اصلاح کنید.",
    },
    "therapy_session_increase_rejected": {
        "sms": "دانشجوی گرامی، درمانگر آموزشی شما در حال حاضر امکان افزایش جلسات هفتگی را ندارد.",
        "in_app": "امکان اضافه کردن جلسه در هفته را ندارم. (نظر درمانگر آموزشی)",
    },
    "therapy_session_increase_sla_therapist": {
        "sms": "یادآوری: درخواست افزایش جلسات هفتگی درمان در پورتال شما در انتظار بررسی است؛ لطفاً تا پایان مهلت اقدام کنید.",
    },
    "therapy_session_increase_reminder_student_response": {
        "sms": "یادآوری: پاسخ شما به پیشنهاد زمانی درمانگر (افزایش جلسات هفتگی) در پورتال ثبت نشده؛ لطفاً تأیید یا زمان جدید ارسال کنید.",
    },
    "supervision_session_increase_request": {
        "sms": "درخواست دانشجو برای افزایش جلسات هفتگی سوپرویژن فردی ثبت شده. لطفاً در پورتال بررسی فرمایید."
    },
    "supervision_session_increase_approved": {
        "in_app": "درخواست افزایش جلسه سوپرویژن تایید شد. روز و ساعت جدید به برنامه سوپرویژن فردی شما اضافه شد.",
    },
    "supervision_session_increase_alternative": {
        "in_app": "سوپروایزر روز و ساعت پیشنهادی دیگری دارد. لطفاً در توضیحات «لطفا روز هفته و ساعت پیشنهادی خود را در توضیحات بنویسید» را ببینید و زمان جدید را وارد کنید."
    },
    "supervision_session_increase_rejected": {
        "sms": "دانشجوی گرامی، پیرو درخواست شما برای اضافه کردن جلسات هفتگی سوپروژن فردی، متاسفانه سوپروایزر شما اعلام کرده است که امکان اضافه کردن جلسات هفتگی را ندارد.",
        "in_app": "امکان برگزاری جلسه اضافه را ندارم. (نظر سوپروایزر)"
    },
    "supervision_session_reduction_eligibility_blocked": {
        "in_app": "دانشجوی گرامی زمانی میتوانید جلسات سوپرویژن خود را به کمتر از یکبار در هفته برسانید که ساعات 150، 250 و 750 به ترتیب برای سوپرویژن فردی، درمان آموزشی و تجربه بالینی را گذرانده باشید."
    },
    "supervision_session_reduction_multi": {
        "sms": "موضوع: کاهش تعداد جلسات هفتگی سوپرویژن فردی. {student_name} جلسه هفتگی خود در روز {day} و ساعت {time} را از برنامه جلسات هفتگی سوپرویژن فردی خود حذف کرده است."
    },
    "supervision_session_reduction_approved": {
        "sms": "درخواست کاهش جلسات سوپرویژن شما تایید شد. روز و ساعات برگزاری جدید در پورتال ثبت شد."
    },
    "supervision_session_reduction_rejected": {
        "sms": "درخواست کاهش توالی جلسات سوپرویژن شما رد شد. لطفاً توضیحات سوپروایزر را در پورتال ببینید و روز و ساعت دیگری ثبت کنید."
    },
    "therapy_session_reduction_blocked": {
        "in_app": "شما امکان کاهش جلسات به کمتر از یک بار در هفته را از این طریق ندارید. در صورت نیاز به قطع موقت، از فرایند وقفه موقت استفاده کنید و در صورت نیاز به درمان با تواتر کمتر، باید از سیستم آموزشی خارج شده و از طریق سایت درمان عمومی اقدام نمایید.",
        "sms": "کاهش جلسات از این مسیر فقط با حداقل ۲ جلسه/هفته ممکن است. برای وقفه از فرایند وقفهٔ درمان استفاده کنید.",
    },
    "therapy_session_reduction_violation_warning": {
        "in_app": "توجه: کاهش جلسات به یک بار در هفته پیش از تکمیل ساعات مصوب، تخلف آموزشی محسوب می‌شود. طبق مقررات، ساعات گذرانده شده در حالت یک جلسه در هفته جزو ۲۵۰ ساعت درمان آموزشی دو بار در هفته برای فارغ‌التحصیلی محاسبه نخواهد شد (ساعات سوخت می‌شود). همچنین گزارش این اقدام جهت ثبت تخلف به کمیته نظارت ارسال می‌گردد.",
        "sms": "هشدار انستیتو: کاهش به ۱ جلسه/هفته پیش از تکمیل ساعات، تخلف آموزشی است. ادامه را در پورتال تأیید کنید.",
    },
    "therapy_session_reduction_completed": {
        "sms": "انستیتو: کاهش جلسات هفتگی درمان آموزشی ثبت شد. برنامهٔ جدید: {new_weekly} جلسه در هفته (قبلاً {old_weekly}). جلسات انتخاب‌شده لغو شدند.",
    },
    "violation_session_reduction": {
        "in_app": "گزارش تخلف آموزشی: دانشجو {student_name} جلسات هفتگی را به یک بار در هفته کاهش داده در حالی که ساعات ۲۵۰/۷۵۰/۱۵۰ تکمیل نشده است. فرایند ثبت تخلف آغاز شد.",
    },
    "therapy_early_termination_standard": {
        "sms": "موضوع: تغییر درمانگر آموزشی. دانشجوی گرامی، با توجه به قطع زودرس درمان آموزشی توسط درمانگر آموزشی تان، لازم است تا ۵ روز از تاریخ دریافت این پیام از فرایند «آغاز دوباره درمان آموزشی یا تغییر زمان یا تغییر درمانگر آموزشی در دوره آشنایی یا جامع» درمانگر آموزشی جدیدی را برای خود انتخاب فرمایید. موفق باشید. انستیتو روانکاوی تهران",
        "in_app": "با توجه به قطع زودرس درمان آموزشی توسط درمانگر آموزشی تان، لازم است تا ۵ روز از تاریخ امروز از فرایند «آغاز دوباره درمان آموزشی یا تغییر زمان یا تغییر درمانگر آموزشی» درمانگر آموزشی جدیدی را انتخاب فرمایید.",
    },
    "violation_no_restart_5days": {
        "in_app": "گزارش تخلف: دانشجو {student_name} ظرف ۵ روز پس از قطع زودرس درمان آموزشی، درمان را از سر نگرفته است. فرایند ثبت تخلفات آغاز شد.",
    },
    "supervision_committee_sla_breach": {
        "in_app": "کمیته نظارت در مهلت مقرر (۳ روز) اطلاعات جلسه را تعیین نکرده است. لطفاً پیگیری فرمایید.",
    },
    "therapist_cancellation_no_makeup": {
        "sms": "جلسه درمان آموزشی توسط درمانگر آموزشی لغو شد. امکان برگزاری جلسه جبرانی وجود ندارد.",
        "in_app": "جلسه درمان آموزشی شما توسط درمانگر لغو شده است. در صورت پرداخت قبلی، یک جلسه به حساب بستانکاری شما اضافه شده است.",
    },
    "makeup_session_proposed": {
        "sms": "درمانگر آموزشی تاریخ و ساعت جلسه جبرانی پیشنهاد کرده است. لطفاً در پورتال تایید یا اصلاح فرمایید.",
        "in_app": "تاریخ و ساعت جلسه جبرانی: {makeup_date} ساعت {makeup_time}. لطفاً تایید، رد و پیشنهاد جدید، یا انصراف را انتخاب کنید.",
    },
    "makeup_alternative_proposed": {
        "in_app": "دانشجو تاریخ و ساعت پیشنهادی را رد کرده و زمان جدید پیشنهاد داده: {student_proposed_time}. لطفاً بررسی و تاریخ/ساعت جدید یا انصراف را ثبت کنید.",
    },
    "student_declined_makeup": {
        "sms": "دانشجو قصد برگزاری جلسه جبرانی را ندارد. جلسه لغو شده تلقی می‌گردد.",
        "in_app": "دانشجو جلسه جبرانی نمی‌خواهد. جلسه لغو شده است.",
    },
    "supervisor_cancellation_no_makeup": {
        "sms": "جلسه سوپرویژن فردی شما توسط سوپروایزر لغو شد. امکان برگزاری جلسه جبرانی وجود ندارد. در صورت پرداخت قبلی، یک جلسه به حساب بستانکاری شما اضافه شده است.",
        "in_app": "جلسه سوپرویژن فردی شما توسط سوپروایزر لغو شده است. امکان برگزاری جلسه جبرانی وجود ندارد. در صورت پرداخت قبلی، یک جلسه به حساب بستانکاری شما اضافه شده است.",
    },
    "supervision_makeup_proposed": {
        "sms": "سوپروایزر شما تاریخ و ساعت جلسه جبرانی سوپرویژن پیشنهاد کرده است. لطفاً در پورتال تایید یا اصلاح فرمایید.",
        "in_app": "سوپروایزر شما برای جلسه کنسل‌شده سوپرویژن، تاریخ {proposed_date} ساعت {proposed_time} را پیشنهاد داده است. لطفاً تایید، رد و پیشنهاد جدید، یا انصراف را انتخاب کنید.",
    },
    "student_supervision_counter_proposal": {
        "sms": "دانشجو تاریخ و ساعت پیشنهادی جلسه جبرانی سوپرویژن را رد کرده و زمان جدید پیشنهاد داده. لطفاً پورتال را بررسی کنید.",
        "in_app": "دانشجو تاریخ و ساعت پیشنهادی را رد کرده و زمان جدید پیشنهاد داده: {student_proposed_text}. لطفاً بررسی و تاریخ/ساعت جدید یا انصراف را ثبت کنید.",
    },
    "student_declined_supervision_makeup": {
        "sms": "دانشجو قصد برگزاری جلسه جبرانی سوپرویژن را ندارد.",
        "in_app": "دانشجو جلسه جبرانی سوپرویژن را نمی‌خواهد. جلسه لغو شده تلقی می‌گردد.",
    },
    "unannounced_absence_reminder": {
        "sms": "دانشجوی محترم، شما باید غیبت خود را در جلسه درمان آموزشی مورخ {session_date} در پورتال خود مطابق فرایند کنسل کردن جلسات درمان آموزشی ثبت می‌کردید. لطفاً در صورت غیبت در جلسات آتی قبل از برگزاری جلسات این فرایند را در پورتال خود اجرا کنید.",
    },
    "unannounced_absence_alert": {
        "in_app": "هشدار: دانشجو {student_name} حداقل ۲ جلسه غیبت بدون اعلام کنسلی داشته است. تاریخ‌های غیبت: {absence_dates}. درمانگر: {therapist_name}. لطفاً با درمانگر تماس گرفته و وضعیت را تعیین کنید.",
    },
    "unannounced_absence_option1_sms": {
        "sms": "دانشجوی گرامی، به واسطه اینکه حداقل دو جلسه غیبت بدون اعلام کنسلی در درمان آموزشی خود داشته‌اید، یادآوری می‌شود اگر قصد غیبت دارید فرایند «کنسل کردن جلسات درمان آموزشی» را تکمیل کنید. اگر غیبت‌ها بیش از سه هفته باشند، فرایند «وقفه موقت» را تکمیل نمایید.",
    },
    "unannounced_absence_option3_sms": {
        "sms": "دانشجوی گرامی، به واسطه ابهامی که در مورد ادامه درمان آموزشی شما به دلیل ۲ جلسه غیبت بدون اعلام کنسلی به وجود آمده، زمان جلسات شما در لیست وقت‌های آزاد قرار گرفته است. در صورت تمایل به برگشت، از فرایند «آغاز درمان آموزشی» در پورتال استفاده کنید.",
    },
    "therapy_terminated_notice": {
        "sms": "دانشجوی گرامی، با ابراز تاسف در مورد قطع شدن درمان آموزشی تان به اطلاع می‌رسانیم که با توجه به اهمیت چنین رخدادی لازم می‌دانیم با شما در آینده‌ای نزدیک تماس بگیریم. با احترام کمیته درمان آموزشی و سوپرویژن.",
    },
    "committee_delegation_message": {
        "in_app": "مسئول پروژه محترم: به واسطه قطع قطعی درمان آموزشی دانشجو {student_name} با درمانگر {therapist_name}، لازم است کار پیگیری را به مجری منتصب واگذار بفرمایید.",
    },
    "supervision_45_48_reminder": {
        "sms": "دانشجوی گرامی. یادآوری میشود که با نزدیک شدن به خاتمه 50 ساعت سوپرویژن خود با سوپروایزر فعلی‌تان، الزامیست که از الان به شناسایی نام سوپروایزر بعدی مورد نظر خود بپردازید، چرا که برای پرداخت و حضور در جلسه پنجاهم با سوپروایزر فعلی‌تان الزامی خواهد بود که نه تنها نام سوپروایزر و زمان جلسات سوپرویژن فردی بعدی‌تان را مشخص کرده باشید، بلکه لازم است که همزمان هزینه جلسه اول با سوپروایزر بعدی پرداخت شود. برای ثبت سوپروایزر بعدی، بعد از 49مین حضور از جلسات سوپرویژن فعلی اقدام فرمایید."
    },
    "supervision_evaluation_warning": {
        "in_app": "سوپروایزر گرامی، از آنجایی که سوپرویژی شما به 50مین حضور خود در این دوره سوپرویژن رسیده است، لازم است ظرف حداکثر 3 روز آینده فرم \"ارزیابی دانشجو بعد از 50 ساعت سوپرویژن فردی\" را تکمیل کنید."
    },
    "supervision_attendance_followup_required": {
        "in_app": "وضعیت جلسه مورخ {date} سوپروایزر {supervisor_name} با دانشجو {student_name} نامشخص است. لطفاً از سوپروایزر پیگیری بفرمایید."
    },
    "supervision_site_manager_delay": {
        "in_app": "مسئول سایت در پیگیری وضعیت جلسه سوپرویژن بدون ثبت حضور یا غیاب اهمال کرده است."
    },
    "supervision_block_transition_complete": {
        "sms": "سوپرویژن فردی جدید: روز {day} ساعت {time} با {supervisor_name}. تاریخ آغاز: {start_date}. انستیتو روانکاوی تهران."
    },
    "therapy_interruption_meeting": {
        "sms": "جزئیات جلسه بررسی درخواست وقفه درمان آموزشی در پورتال و ایمیل شما موجود است. لطفاً مراجعه فرمایید.",
        "email_subject": "تعیین زمان جلسه بررسی درخواست وقفه درمان آموزشی",
        "email_body": "دانشجوی گرامی، تاریخ و ساعت جلسه بررسی درخواست وقفه درمان آموزشی شما تعیین شده است. لطفاً به پورتال مراجعه کنید."
    },
    "therapy_interruption_rejected": {
        "in_app": "گزارش رد درخواست وقفه درمان آموزشی دانشجو {student_name}. فرایند ثبت تخلفات آغاز شد."
    },
    "committee_delegation_ambiguous": {
        "in_app": "مسئول پروژه محترم: به واسطه ابهام در مورد ادامه درمان دانشجو {student_name} و عدم بازگشت ظرف ۳ هفته، قطع درمان قطعی لحاظ شده. لطفاً پیگیری را به مجری واگذار بفرمایید.",
    },
    "education_termination_notice": {
        "sms": "دانشجوی گرامی، نتیجه بررسی کمیته آموزش در خصوص پرونده قطع زودرس درمان آموزشی به اطلاع شما می‌رسد. لطفاً به پورتال مراجعه کنید.",
        "email_subject": "اعلام نتیجه کمیته آموزش",
        "email_body": "دانشجوی گرامی، نتیجه نهایی بررسی کمیته آموزش در خصوص پرونده شما ابلاغ گردیده است. نامه رسمی در پرونده دیجیتال شما موجود است.",
    },
    "fee_settled": {
        "sms": "هزینه جلسه تسویه شد.",
    },
    "debt_registered": {
        "sms": "بدهی غیبت جلسه ثبت شد. لطفاً تسویه فرمایید.",
    },
    "fee_dispute": {
        "email_subject": "اعتراض به هزینه جلسه",
        "email_body": "دانشجو نسبت به هزینه جلسه اعتراض کرده است.",
    },
    "fee_waived": {
        "sms": "هزینه جلسه بخشیده شد.",
    },
    "dispute_rejected": {
        "sms": "اعتراض شما به هزینه جلسه رد شد.",
    },
    "sla_breach_warning": {
        "sms": "هشدار: زمان SLA برای بررسی درخواست در حال اتمام است.",
    },
    "sla_breach": {
        "sms": "اخطار SLA: زمان مجاز بررسی درخواست به پایان رسیده است.",
    },
    "committee_sla_breach": {
        "sms": "معاون محترم مدیر آموزش، کمیته پیشرفت موظف بوده است که در طی 7 روز جلسه‌ای را با دانشجوی متقاضی وقفه در کلاس‌ها تنظیم کند، اما چنین اقدامی صورت نگرفته است.",
    },
    "meeting_scheduled": {
        "email_subject": "تعیین زمان جلسه کمیته پیشرفت",
        "email_body": "دانشجوی گرامی، زمان و مکان جلسه بررسی درخواست وقفه شما تعیین شده است.\n{meeting_summary_fa}\nلطفاً به پورتال مراجعه کنید.",
    },
    "meeting_scheduled_sms": {
        "sms": "زمان جلسه کمیته پیشرفت برای درخواست وقفه تعیین شد.\n{meeting_summary_fa}\nلطفاً به پورتال مراجعه کنید.",
    },
    "leave_rejected_committee_alert": {
        "sms": "گزارش عدم تایید وقفه در کلاس‌ها ثبت شد. لطفاً در پورتال کمیته نظارت بررسی فرمایید.",
    },
    "intern_2term_referral_started": {
        "sms": "فرایند ارجاع بیماران انترن به درمانگران دیگر برای دانشجوی وقفه ۲ ترمی آغاز شد. لطفاً در پورتال کمیته نظارت بررسی فرمایید.",
    },
    "therapy_already_used": {
        "sms": "دانشجوی گرامی، شما قبلاً از این فرایند برای شروع درمان آموزشی استفاده کرده‌اید.",
    },
    "therapy_scheduled_student": {
        "sms": "دانشجوی گرامی\nموضوع: زمان‌بندی آغاز درمان آموزشی\nبه اطلاع می‌رساند که وقت شما برای درمان آموزشی با آقای/خانم ...، روز... ساعت... و روز... ساعت... با تاریخ آغاز... ثبت شده است.\nمسئول هماهنگی‌ها ۰۲۱۲۲۷۲۸۰۰۰ داخلی ۱",
    },
    "therapy_scheduled_therapist": {
        "sms": "درمانگر آموزشی محترم\nموضوع: آغاز درمان آموزشی دانشجو\nبه اطلاع می‌رساند که آقای/خانم ... دانشجوی دوره... درخواست آغاز درمان آموزشی خود را با شما در روز... ساعت... و روز... ساعت... و تاریخ آغاز... ثبت کرده‌اند.\nمسئول هماهنگی‌ها ۰۲۱۲۲۷۲۸۰۰ داخلی ۱",
    },
    "start_therapy_sla_therapist_pending": {
        "sms": "یادآوری آغاز درمان آموزشی: درخواست شما هنوز در انتظار پاسخ درمانگر است. لطفاً پورتال دانشجویی را بررسی کنید.",
    },
    "start_therapy_sla_payment_pending": {
        "sms": "یادآوری آغاز درمان آموزشی: پرداخت جلسهٔ اول در پورتال شما ناقص است. از مسیر «پرداخت» همان صفحه اقدام کنید.",
    },
    "supervision_interruption_meeting_invite": {
        "sms": "جزئیات جلسه بررسی درخواست وقفه سوپرویژن فردی در پورتال شما موجود است. لطفاً مراجعه فرمایید.",
        "in_app": "زمان جلسه بررسی درخواست وقفه سوپرویژن فردی شما تعیین شد: تاریخ {date} ساعت {time}. نوع برگزاری: {meeting_type}.",
    },
    "supervision_interruption_rejected": {
        "in_app": "درخواست وقفه سوپرویژن فردی شما رد شد. توضیحات کمیته: {explanation}. موضوع جهت بررسی به کمیته نظارت ارجاع شد.",
    },
    "supervision_interruption_approved": {
        "in_app": "درخواست وقفه سوپرویژن فردی شما تایید شد. بازه وقفه: {start_date} تا {end_date}.",
    },
    "semester_registration_reminder": {
        "sms": "دانشجوی محترم\nموضوع: مهلت ثبت نام\nبه اطلاع میرسانیم که مهلت ثبت نام برای ترم {term_name} تاریخ {deadline} می باشد. برای ثبت نام لطفا به لینک زیر مراجعه بفرمایید:\n{link}\nمسئول هماهنگی ها\n۰۲۱۲۲۷۲۸۰۰۰\nداخلی ۱",
    },
    "sla_warning_non_blocking": {
        "in_app": "{warning_message}",
    },
    "interview_confirmation_applicant": {
        "sms": "متقاضی محترم\nموضوع: وقت مصاحبه دوره {course_type}\nوقت شما برای مصاحبه پذیرش در تاریخ {date} ساعت {time} ثبت گردید.\n{location_info}\nموفق باشید\nبخش پذیرش\n۰۹۱۲۲۲۰۶۷۹۶",
    },
    "interview_confirmation_interviewer": {
        "sms": "هیئت علمی محترم انستیتو روانکاوی تهران\nموضوع: وقت مصاحبه دوره {course_type}\nباطلاع میرسانیم در تاریخ {date} ساعت {time} مصاحبه با آقای/خانم {applicant_name} برای ورود به دوره برنامه ریزی شده است.\n{location_info}\nبا تشکر\nبخش پذیرش\n۰۹۱۲۲۲۰۶۷۹۶",
    },
    "interview_reminder_2h": {
        "sms": "یادآوری: دو ساعت دیگر وقت مصاحبه شما در تاریخ {date} ساعت {time} می باشد. {location_info}",
    },
    "admission_result_conditional": {
        "sms": "متقاضی گرامی\nموضوع: پذیرش در دوره آشنایی\nمفتخریم که به اطلاعتان برسانیم که شما پذیرفته شده اید.\nشرایط: ثبت نام در ترم دوم مشروط به آغاز درمان شخصی حداقل یک بار در هفته قبل از آغاز ترم دوم.\nمهلت ثبت نام و پرداخت شهریه تا {deadline}.\nکمیته پذیرش انستیتو روانکاوی تهران",
    },
    "admission_result_single_course": {
        "sms": "متقاضی گرامی\nموضوع: پذیرش در دوره آشنایی\nمفتخریم که به اطلاعتان برسانیم که شما پذیرفته شده اید.\nشما میتوانید فقط برای تک درس تئوری روانکاوی (۱) ثبت نام بفرمایید.\nمهلت ثبت نام و پرداخت شهریه تا {deadline}.\nکمیته پذیرش انستیتو روانکاوی تهران",
    },
    "admission_result_full": {
        "sms": "متقاضی گرامی\nموضوع: پذیرش در دوره آشنایی\nمفتخریم که به اطلاعتان برسانیم که شما پذیرفته شده اید.\nشما می توانید برای هر تعداد یا تمام دروس این ترم ثبت نام بفرمایید.\nمهلت ثبت نام و پرداخت شهریه تا {deadline}.\nکمیته پذیرش انستیتو روانکاوی تهران",
    },
    "admission_result_rejected": {
        "sms": "متقاضی گرامی\nموضوع: پذیرش در دوره آشنایی\nبا کمال تاسف به اطلاع جنابعالی میرسانیم که در فرایند پذیرش پذیرفته نشده اید.\nاز صمیم قلب آرزوی موفقیت شما را داریم.\nکمیته پذیرش انستیتو روانکاوی تهران",
    },
    "document_upload_request": {
        "sms": "متقاضی محترم\nموضوع: بارگزاری مدارک\nلطفا تا تاریخ {deadline} مدارک لازم را در سایت ثبت نام انستیتو بارگزاری فرمایید.\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "documents_approved_credentials": {
        "sms": "متقاضی محترم\nموضوع: پرتال دانشجویی و ثبت نام\nمدارک شما تایید شد. تا تاریخ {deadline} با اطلاعات زیر وارد پرتال شوید:\nUSERNAME: {username}\nPASSWORD: {password}\nموفق باشید\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "documents_incomplete": {
        "sms": "متقاضی محترم\nموضوع: اصلاح مدارک\nتا تاریخ {deadline} مهلت دارید مدارک زیر را دوباره بارگزاری کنید:\n{deficiency_list}\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "installment_reminder": {
        "sms": "دانشجوی محترم\nموضوع: مهلت پرداخت قسط\nمهلت پرداخت قسط بعدی شما به مبلغ {amount}، تاریخ {due_date} می باشد. عدم پرداخت بموقع موجب عدم اجازه حضور در کلاسها خواهد شد.\nمسئول هماهنگی ها ۰۲۱۲۲۷۲۸۰۰۰ داخلی ۱",
    },
    "therapy_condition_block": {
        "sms": "دانشجوی محترم\nموضوع: شرط ثبت نام در ترم دوم\nطبق توافق قبلی در مورد پذیرش شما، می بایست وارد درمان شخصی شوید. لطفا از فرایند «آغاز درمان آموزشی» در پورتال اقدام بفرمایید.\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "term_registration_general": {
        "sms": "دانشجوی محترم\nموضوع: مهلت ثبت نام در ترم ها\nمهلت ثبت نام در دروس ترم بعدی تاریخ {deadline} می باشد. لطفا زودتر اقدام بفرمایید.\nمسئول هماهنگی ها ۰۲۱۲۲۷۲۸۰۰۰ داخلی ۱",
    },
    "introductory_completion_invitation": {
        "sms": "دانشجوی گرامی\nموضوع: درخواست ورود به دوره جامع\nبه اطلاع میرساند که مهلت شما برای درخواست ورود به دوره جامع رواندرمانی تحلیلی در انستیتو روانکاوی تهران، تاریخ {deadline} می باشد.\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "certificate_ready": {
        "sms": "دانشجوی گرامی\nموضوع: صدور گواهی پایان دوره\nبا تبریک اتمام موفقیت‌آمیز دوره آشنایی، گواهی پایان دوره شما صادر و در پورتال آموزشی (LMS) آماده دانلود می‌باشد.\nانستیتو روانکاوی تهران",
    },
    "comprehensive_admission_accepted": {
        "sms": "دانشجوی گرامی\nموضوع: پذیرش در دوره جامع\nمفتخریم که به اطلاعتان برسانیم که در دوره جامع رواندرمانی تحلیلی پذیرفته شده اید.\nشرایط: درمان آموزشی حداقل ۲ بار در هفته + ثبت نام در تمامی دروس اجباری.\nمهلت ثبت نام تا {deadline}.\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "comprehensive_admission_rejected": {
        "sms": "متقاضی گرامی\nموضوع: پذیرش در دوره جامع\nبا کمال تاسف به اطلاع جنابعالی میرسانیم که در فرایند پذیرش به دوره جامع پذیرفته نشده اید.\nاز صمیم قلب آرزوی موفقیت شما را داریم.\nبخش پذیرش ۰۹۱۲۲۲۰۶۷۹۶",
    },
    "mentor_sessions_registered": {
        "sms": "تاریخ ۲ جلسه تدریس خصوصی مدرس به کمک‌مدرس ثبت شد. جزئیات در پورتال.",
    },
    "ta_to_assistant_faculty_congrats": {
        "sms": "تبریک! رتبه شما به دستیار هیئت علمی ارتقا یافت.",
    },
    "ta_to_instructor_auto_congrats": {
        "sms": "تبریک! شما به عنوان مدرس در درس {course_name} منصوب شدید.",
    },
    "ta_track_completion_congrats": {
        "sms": "تبریک! رسته کمک‌مدرس شما با موفقیت خاتمه یافت.",
    },
    "ta_track_meeting_scheduled": {
        "sms": "زمان جلسه کمیته دروس برای تغییر/اضافه رسته کمک‌مدرس تعیین شد. لطفاً به پورتال مراجعه کنید.",
    },
    "mentor_sessions_deadline_violation": {
        "sms": "هشدار: تاریخ ۲ جلسه تدریس خصوصی مدرس به کمک‌مدرس تا شروع جلسه دوم ثبت نشده. تخلف ثبت شد.",
    },
}


class NotificationService:
    """Service for sending notifications via SMS, Email, etc."""

    def __init__(self):
        self._sent_log: list[NotificationResult] = []

    def get_template(self, template_name: str, notification_type: str = "sms") -> Optional[str]:
        """Get a notification template message."""
        template = TEMPLATES.get(template_name, {})
        if notification_type == "sms":
            return template.get("sms")
        elif notification_type == "email":
            return template.get("email_body")
        elif notification_type == "in_app":
            return template.get("in_app")
        return None

    async def send_sms(self, phone: str, message: str) -> NotificationResult:
        """Send an SMS message via the configured gateway."""
        from app.services.sms_gateway import send_sms as gateway_send
        gateway_result = await gateway_send(phone, message)
        success = gateway_result.get("success", False)
        result = NotificationResult(
            success=success,
            notification_type="sms",
            recipient=phone,
            message=message,
            error="" if success else gateway_result.get("error", "unknown"),
        )
        self._sent_log.append(result)
        return result

    async def send_email(self, email: str, subject: str, body: str) -> NotificationResult:
        """Send an email (placeholder - logs instead of sending)."""
        logger.info(f"[EMAIL] To: {email} | Subject: {subject} | Body: {body[:100]}...")
        result = NotificationResult(
            success=True,
            notification_type="email",
            recipient=email,
            message=f"{subject}: {body}",
        )
        self._sent_log.append(result)
        return result

    async def send_notification(
        self,
        notification_type: str,
        template_name: str,
        recipient_contact: str,
        context: Optional[dict] = None,
    ) -> NotificationResult:
        """Send a notification using a template."""
        message = self.get_template(template_name, notification_type)
        if not message:
            return NotificationResult(
                success=False,
                notification_type=notification_type,
                recipient=recipient_contact,
                error=f"Template '{template_name}' not found for type '{notification_type}'",
            )

        # Simple template variable replacement
        if context:
            for key, value in context.items():
                message = message.replace(f"{{{key}}}", str(value))

        if notification_type == "sms":
            return await self.send_sms(recipient_contact, message)
        elif notification_type == "email":
            subject = TEMPLATES.get(template_name, {}).get("email_subject", "Notification")
            return await self.send_email(recipient_contact, subject, message)
        elif notification_type == "in_app":
            logger.info(
                "[IN_APP] to=%s template=%s msg=%s",
                recipient_contact,
                template_name,
                (message or "")[:200],
            )
            return NotificationResult(
                success=True,
                notification_type="in_app",
                recipient=recipient_contact,
                message=message or "",
            )
        else:
            logger.warning(f"Unknown notification type: {notification_type}")
            return NotificationResult(
                success=False,
                notification_type=notification_type,
                recipient=recipient_contact,
                error=f"Unknown notification type: {notification_type}",
            )

    async def process_transition_actions(self, actions: list[dict], context: dict = None):
        """Process notification actions from a transition's action list."""
        results = []
        for action in actions:
            if action.get("type") == "notification":
                ntype = action.get("notification_type", "sms")
                template = action.get("template", "")
                recipients = action.get("recipients", [])
                for recipient_role in recipients:
                    contact = (context or {}).get(f"{recipient_role}_contact", f"mock_{recipient_role}")
                    result = await self.send_notification(ntype, template, contact, context)
                    results.append(result)
        return results

    def get_sent_log(self) -> list[dict]:
        """Get the log of sent notifications (useful for testing)."""
        return [r.to_dict() for r in self._sent_log]

    def clear_log(self):
        """Clear the sent notification log."""
        self._sent_log.clear()


# Singleton
notification_service = NotificationService()
