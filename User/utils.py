from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
import hashlib
from django.conf import settings
import time
from django.utils.html import strip_tags
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
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email: {str(e)}")
        return False
    
def send_business_verification_submitted_email(user):
    """Send confirmation email when business verification is submitted"""
    try:
        subject = "Business Verification Application Submitted - OpenSell"
        
        email_context = {
            'user': user,
            'business_name': user.profile.business_name,
            'site_url': settings.SITE_URL,
            'site_name': settings.SITE_NAME,
            'status_url': settings.SITE_URL + reverse('business_verification_status'),
        }
        
        html_message = render_to_string('emails/business_verification_submitted.html', email_context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Business verification submitted email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send business verification submitted email to {user.email}: {str(e)}")
        return False

def send_business_verification_approved_email(user, verified_by_admin):
    try:
        subject = "🎉 Your Business Has Been Verified - OpenSell"
        
        email_context = {
            'user': user,
            'business_name': user.profile.business_name,
            'verified_date': user.profile.business_verified_at,
            'site_url': settings.SITE_URL,
            'site_name': settings.SITE_NAME,
            'store_url': settings.SITE_URL + reverse('user_store', kwargs={'username': user.username}),
            'benefits': [
                'Verified business badge on all your products',
                'Access to permanent retail listings',
                'Enhanced business profile visibility',
                'Display business address and contact info',
                'Priority in search results',
                'Access to business-only filters'
            ]
        }
        
        html_message = render_to_string('emails/business_verification_approved.html', email_context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Business verification approved email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send business verification approved email to {user.email}: {str(e)}")
        return False

def send_business_verification_rejected_email(user, rejection_reason=None):
    """Send email when business verification is rejected"""
    try:
        subject = "Business Verification Update - OpenSell"
        
        email_context = {
            'user': user,
            'business_name': user.profile.business_name,
            'rejection_reason': rejection_reason,
            'site_url': settings.SITE_URL,
            'site_name': settings.SITE_NAME,
            'reapply_url': settings.SITE_URL + reverse('business_verification_form'),
            'support_email': settings.DEFAULT_FROM_EMAIL,
        }
        
        html_message = render_to_string('emails/business_verification_rejected.html', email_context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        logger.info(f"Business verification rejected email sent to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send business verification rejected email to {user.email}: {str(e)}")
        return False