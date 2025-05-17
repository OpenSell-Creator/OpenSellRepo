from django.core.mail import send_mail as django_send_mail
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
import hashlib
import time
import logging
logger = logging.getLogger(__name__)

def user_directory_path(instance, filename):
    return f'profile_pictures/{instance.user.username}/{filename}'

def get_unsubscribe_token(user):
    """Get or create an unsubscribe token for a user"""
    try:
        # Get the user's profile and email preferences
        profile = user.profile
        preferences = profile.get_or_create_email_preferences()
        return preferences.unsubscribe_token
    except Exception as e:
        logger.error(f"Failed to get unsubscribe token: {str(e)}")
        return None

def send_mail(subject, message, from_email, recipient_list, html_message=None, fail_silently=False, **kwargs):
    """
    Extended send_mail function that adds unsubscribe functionality to html emails
    """
    # Only process html messages for single recipients that are registered users
    if html_message and len(recipient_list) == 1:
        try:
            from django.contrib.auth.models import User
            user = User.objects.get(email=recipient_list[0])
            
            # Get unsubscribe token for this user
            unsubscribe_token = get_unsubscribe_token(user)
            
            # Add unsubscribe context to the html message if it's a template string
            if unsubscribe_token and '{{' in html_message:
                # Extract any existing context from kwargs
                context = kwargs.get('context', {})
                
                # Add unsubscribe token to context
                context['unsubscribe_token'] = unsubscribe_token
                context['user'] = user
                
                # Add protocol and domain if not present
                if 'protocol' not in context:
                    context['protocol'] = 'https'  # Defaulting to https
                if 'domain' not in context:
                    context['domain'] = settings.SITE_DOMAIN
                
                # Render template with updated context
                html_message = render_to_string(html_message, context)
        except Exception as e:
            logger.warning(f"Could not add unsubscribe info to email: {str(e)}")
    
    # Send the email using Django's send_mail
    return django_send_mail(subject, message, from_email, recipient_list, 
                          html_message=html_message, fail_silently=fail_silently)

def send_otp_email(user):
    """Send OTP verification email to user"""
    try:
        # Generate new OTP
        otp = user.profile.generate_otp()
        
        # Get unsubscribe token
        unsubscribe_token = get_unsubscribe_token(user)
        
        subject = "Your Email Verification OTP"
        message = f"Your OTP for email verification is: {otp}. It will expire in 10 minutes."
        
        context = {
            'user': user,
            'otp': otp,
            'protocol': 'https',
            'domain': settings.SITE_DOMAIN,
            'unsubscribe_token': unsubscribe_token
        }
        
        html_message = render_to_string('otp_email.html', context)
        
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