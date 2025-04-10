from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string


def user_directory_path(instance, filename):
    return f'profile_pictures/{instance.user.username}/{filename}'


def send_otp_email(user):
    """Send OTP verification email to user"""
    # Generate new OTP
    otp = user.profile.generate_otp()
    
    subject = "Your Email Verification OTP"
    message = f"Your OTP for email verification is: {otp}. It will expire in 10 minutes."
    html_message = render_to_string('otp_email.html', {
        'user': user,
        'otp': otp
    })
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        html_message=html_message,
        fail_silently=False,
    )
    return True
