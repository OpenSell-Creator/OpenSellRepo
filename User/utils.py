from django.core.mail import send_mail as django_send_mail
from django.utils import timezone
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils.html import strip_tags
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
    Enhanced send_mail function that properly formats HTML emails with unsubscribe functionality
    """
    try:
        # Only process html messages for single recipients that are registered users
        if html_message and len(recipient_list) == 1:
            try:
                from django.contrib.auth.models import User
                user = User.objects.get(email=recipient_list[0])
                
                # Get unsubscribe token for this user
                unsubscribe_token = get_unsubscribe_token(user)
                
                # Extract any existing context from kwargs
                context = kwargs.get('context', {})
                
                # Add unsubscribe token and user to context
                if unsubscribe_token:
                    context['unsubscribe_token'] = unsubscribe_token
                    context['user'] = user
                
                # Add protocol and domain if not present
                if 'protocol' not in context:
                    context['protocol'] = 'https'  # Defaulting to https
                if 'domain' not in context:
                    context['domain'] = settings.SITE_DOMAIN
                
                # If html_message is a template path, render it with context
                if isinstance(html_message, str) and html_message.endswith('.html'):
                    html_message = render_to_string(html_message, context)
            except Exception as e:
                logger.warning(f"Could not add unsubscribe info to email: {str(e)}")
        
        # Create a plain text version if we have HTML
        if html_message:
            plain_message = strip_tags(html_message) if message is None else message
        else:
            plain_message = message
            
        # Create email message with multipart alternatives
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=from_email,
            to=recipient_list
        )
        
        # Attach HTML version with proper content type if provided
        if html_message:
            email.attach_alternative(html_message, "text/html")
            
        # Send the email
        return email.send(fail_silently=fail_silently)
        
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        if not fail_silently:
            raise
        return 0

def send_otp_email(user):
    """Send OTP verification email to user"""
    try:
        # Generate new OTP
        otp = user.profile.generate_otp()
        
        # Get unsubscribe token
        unsubscribe_token = get_unsubscribe_token(user)
        
        subject = "Your Email Verification OTP"
        
        context = {
            'user': user,
            'otp': otp,
            'protocol': 'https',
            'domain': settings.SITE_DOMAIN,
            'unsubscribe_token': unsubscribe_token
        }
        
        # Render HTML message
        html_message = render_to_string('otp_email.html', context)
        
        # Create plain text version
        plain_message = f"Your OTP for email verification is: {otp}. It will expire in 10 minutes."
        
        # Send with proper HTML formatting
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.NO_REPLY_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_message, "text/html")
        email.send(fail_silently=False)
        
        return True
    except Exception as e:
        logger.error(f"Failed to send OTP email: {str(e)}")
        return False