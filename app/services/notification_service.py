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
    "extra_session_rejected": {
        "sms": "درخواست جلسه اضافی رد شد.",
    },
    "extra_session_cancelled": {
        "sms": "جلسه اضافی لغو شد.",
    },
    "extra_session_payment_timeout": {
        "sms": "مهلت پرداخت جلسه اضافی تمام شد. جلسه لغو شد.",
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
    "sessions_suspended": {
        "sms": "جلسات درمان به دلیل عدم پرداخت معلق شد.",
    },
    "session_reminder": {
        "sms": "یادآوری: جلسه درمان آموزشی شما در ساعت آینده برگزار می‌شود.",
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
        return None

    async def send_sms(self, phone: str, message: str) -> NotificationResult:
        """Send an SMS message (placeholder - logs instead of sending)."""
        logger.info(f"[SMS] To: {phone} | Message: {message}")
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient=phone,
            message=message,
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
