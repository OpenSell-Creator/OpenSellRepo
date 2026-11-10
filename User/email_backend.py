"""
Counts every email the provider accepts, per UTC day, so the bulk sender can see how much of the shared daily
quota OTP, welcome, verification, allauth and other emails already used.

Install: EMAIL_BACKEND = 'User.email_backend.CountingSMTPBackend'   (production block of settings.py only)

Counting never blocks mail: if the counter cannot be written, the email still goes out and the error is logged.
"""
import datetime
import logging

from django.core.mail.backends import smtp
from django.db import IntegrityError
from django.db.models import F
from django.utils import timezone

logger = logging.getLogger(__name__)


def record_emails_sent(n):
    if n <= 0:
        return
    try:
        from .models import EmailSendCounter
        day = timezone.now().astimezone(datetime.timezone.utc).date()
        if not EmailSendCounter.objects.filter(day=day).update(total=F('total') + n):
            try:
                EmailSendCounter.objects.create(day=day, total=n)
            except IntegrityError:      # another process created the row first
                EmailSendCounter.objects.filter(day=day).update(total=F('total') + n)
    except Exception:
        logger.warning('Could not record %s sent email(s) in the daily counter', n, exc_info=True)


class CountingMixin:
    def send_messages(self, email_messages):
        sent = super().send_messages(email_messages)
        record_emails_sent(sent or 0)
        return sent


class CountingSMTPBackend(CountingMixin, smtp.EmailBackend):
    pass
