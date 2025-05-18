from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
import hashlib
from django.conf import settings
import time
import logging
logger = logging.getLogger(__name__)

def user_directory_path(instance, filename):
    return f'profile_pictures/{instance.user.username}/{filename}'

def send_otp_email(user):
    """Send OTP verification email to user"""
    try:
        # Generate new OTP
        otp = user.profile.generate_otp()
        
        # Get or create email preferences for unsubscribe links
        preferences = user.profile.get_or_create_email_preferences()
        
        subject = "Your Email Verification OTP"
        # Plain text version
        message = f"Your OTP for email verification is: {otp}. It will expire in 10 minutes."
        
        # HTML version - ensure site_url is passed
        site_url = settings.SITE_URL  # You need to add this to your settings.py
        html_message = render_to_string('otp_email.html', {
            'user': user,
            'otp': otp,
            'site_url': site_url
        })
        
        send_mail(
            subject,
            message,
            settings.NO_REPLY_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email: {str(e)}")
        return False