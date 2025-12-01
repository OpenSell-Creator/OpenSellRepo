from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
import hashlib
from django.conf import settings
import time
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
import logging
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)


def user_directory_path(instance, filename):
    return f'profile_pictures/{instance.user.username}/{filename}'

def send_welcome_email(user):
    """
    Send welcome email to newly registered user
    Introduces platform and encourages business verification
    """
    try:
        from django.core.mail import EmailMultiAlternatives
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from django.urls import reverse
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Get or create email preferences for unsubscribe links
        preferences = user.profile.get_or_create_email_preferences()
        
        subject = f"Welcome to {settings.SITE_NAME} - Get Started!"
        
        # Context for email template
        email_context = {
            'user': user,
            'first_name': user.first_name or user.username,
            'site_url': settings.SITE_URL,
            'site_name': settings.SITE_NAME,
            'profile_url': settings.SITE_URL + reverse('profile_update'),
            'store_url': settings.SITE_URL + reverse('user_store', kwargs={'username': user.username}),
            'verification_url': settings.SITE_URL + reverse('business_verification_form'),
            'product_create_url': settings.SITE_URL + reverse('product_create'),
            'preferences_url': preferences.get_absolute_preferences_url() if preferences else '#',
            'benefits': [
                'Verified business badge on all your listings',
                'Access to permanent retail listings (never expire)',
                'Enhanced visibility in search results',
                'Display business address and contact information',
                'Priority in marketplace rankings',
                'Build customer trust and credibility',
                'Access to business-only features',
                'Priority customer support'
            ],
            'quick_start_steps': [
                {
                    'icon': 'person-circle',
                    'title': 'Complete Your Profile',
                    'description': 'Add your photo, bio, and contact information',
                    'url': reverse('profile_update')
                },
                {
                    'icon': 'shield-check',
                    'title': 'Verify Your Email',
                    'description': 'Confirm your email address for security',
                    'action': 'Check your inbox for verification'
                },
                {
                    'icon': 'box-seam',
                    'title': 'List Your First Product',
                    'description': 'Start selling by creating your first listing',
                    'url': reverse('product_create')
                },
                {
                    'icon': 'building-check',
                    'title': 'Get Business Verified',
                    'description': 'Unlock premium features and build trust',
                    'url': reverse('business_verification_form')
                }
            ]
        }
        
        # Render HTML email
        html_message = render_to_string('emails/welcome_email.html', email_context)
        plain_message = strip_tags(html_message)
        
        # Create email
        email = EmailMultiAlternatives(
            subject=subject,
            body=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach_alternative(html_message, "text/html")
        
        # Send email
        email.send(fail_silently=False)
        
        logger.info(f"Welcome email sent successfully to {user.email}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send welcome email to {user.email}: {str(e)}")
        return False

def send_otp_email(user):
    """Send OTP verification email to user"""
    try:
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.conf import settings
        
        # Generate new OTP
        otp = user.profile.generate_otp()
        
        # Get or create email preferences for unsubscribe links
        preferences = user.profile.get_or_create_email_preferences()
        
        subject = "Your Email Verification OTP"
        # Plain text version
        message = f"Your OTP for email verification is: {otp}. It will expire in 10 minutes."
        
        # HTML version - ensure site_url is passed
        site_url = settings.SITE_URL
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
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from django.urls import reverse
        
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
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from django.urls import reverse
        
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
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.utils.html import strip_tags
        from django.conf import settings
        from django.urls import reverse
        
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

# ============================================================================
# BULK EMAIL SYSTEM - FIXED VERSION
# ============================================================================

def send_bulk_email_task(email_id):
    """
    Background task to send bulk email
    FIXED: Removed .select_related('profile') which was causing the query error
    """
    from User.models import BulkEmail
    from django.contrib.auth.models import User
    from django.utils import timezone
    
    logger.info(f"Starting bulk email task for campaign {email_id}")
    
    try:
        email_campaign = BulkEmail.objects.get(id=email_id)
        
        # Update status to sending
        email_campaign.status = 'sending'
        email_campaign.save(update_fields=['status'])
        logger.info(f"Campaign {email_id} status updated to 'sending'")
        
        # Get recipients query (NOT executed yet - very fast)
        recipients_query = email_campaign.get_recipients_query()
        
        # Process in chunks to avoid memory issues
        CHUNK_SIZE = 50
        total_sent = 0
        total_failed = 0
        
        # FIXED: Get just IDs first, then fetch users WITHOUT select_related
        user_ids = list(recipients_query.values_list('id', flat=True))
        total_users = len(user_ids)
        
        logger.info(f"Campaign {email_id}: Found {total_users} recipients")
        
        # Process in chunks
        for i in range(0, total_users, CHUNK_SIZE):
            chunk_ids = user_ids[i:i + CHUNK_SIZE]
            
            # FIXED: Fetch users WITHOUT select_related to avoid conflict
            chunk_users = User.objects.filter(id__in=chunk_ids)
            
            for user in chunk_users:
                try:
                    send_single_email(user, email_campaign)
                    total_sent += 1
                    
                    # Update progress every 50 emails
                    if total_sent % 50 == 0:
                        email_campaign.total_sent = total_sent
                        email_campaign.save(update_fields=['total_sent'])
                        logger.info(f"Campaign {email_id}: Sent {total_sent}/{total_users} emails")
                        
                except Exception as e:
                    total_failed += 1
                    logger.error(f"Failed to send to {user.email}: {str(e)}")
                    continue
        
        # Mark as complete
        email_campaign.status = 'sent'
        email_campaign.total_sent = total_sent
        email_campaign.sent_at = timezone.now()
        email_campaign.save(update_fields=['status', 'total_sent', 'sent_at'])
        
        logger.info(f"Campaign {email_id} completed: {total_sent} sent, {total_failed} failed")
        
        return {
            'success': True, 
            'sent': total_sent, 
            'failed': total_failed
        }
        
    except BulkEmail.DoesNotExist:
        logger.error(f"Campaign {email_id} not found")
        return {'success': False, 'error': 'Campaign not found'}
        
    except Exception as e:
        logger.error(f"Bulk email {email_id} failed: {str(e)}", exc_info=True)
        try:
            email_campaign.status = 'draft'
            email_campaign.save(update_fields=['status'])
        except:
            pass
        return {'success': False, 'error': str(e)}

def send_single_email(user, campaign):
    """
    Send email to single user - optimized for speed
    """
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings
    import re
    
    # Get user's email preferences to generate unsubscribe link
    try:
        prefs = user.profile.email_preferences
    except:
        # If no preferences, skip this user (they shouldn't receive emails)
        logger.warning(f"User {user.username} has no email preferences, skipping")
        return
    
    # Simple variable replacement (faster than template rendering)
    first_name = user.first_name or user.username
    
    subject = campaign.subject.replace('{{first_name}}', first_name)
    message = campaign.message.replace('{{first_name}}', first_name)
    message = message.replace('{{username}}', user.username)
    message = message.replace('{{site_name}}', settings.SITE_NAME)
    message = message.replace('{{site_url}}', settings.SITE_URL)
    
    # Wrap in simple template
    html_content = wrap_email_simple(message, user)
    plain_content = strip_html_simple(message)
    
    # Send email
    email = EmailMultiAlternatives(
        subject=subject,
        body=plain_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)
    
    logger.debug(f"Email sent to {user.email}")

def wrap_email_simple(content, user):
    """
    Simple HTML wrapper - no template rendering for speed
    """
    from django.conf import settings
    from django.utils import timezone
    
    # Get unsubscribe URL
    try:
        prefs = user.profile.email_preferences
        unsub_url = f"{settings.SITE_URL}/email-preferences/?user={user.id}&token={prefs.unsubscribe_token}"
    except:
        unsub_url = f"{settings.SITE_URL}/email-preferences/"
    
    # Simple HTML structure
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #0d6efd 0%, #6610f2 100%); color: white; padding: 30px 20px; text-align: center; }}
        .content {{ padding: 30px 20px; }}
        .footer {{ background: #f8f9fa; padding: 20px; text-align: center; font-size: 12px; color: #6c757d; border-top: 1px solid #dee2e6; }}
        .footer a {{ color: #0d6efd; text-decoration: none; }}
        .btn {{ display: inline-block; padding: 10px 20px; background: #0d6efd; color: white; text-decoration: none; border-radius: 5px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{settings.SITE_NAME}</h1>
        </div>
        <div class="content">
            {content}
        </div>
        <div class="footer">
            <p>© {timezone.now().year} {settings.SITE_NAME}. All rights reserved.</p>
            <p>
                <a href="{unsub_url}">Manage Email Preferences</a> | 
                <a href="{settings.SITE_URL}">Visit Website</a>
            </p>
        </div>
    </div>
</body>
</html>"""
    
    return html

def strip_html_simple(html):
    """Fast HTML stripping for plain text version"""
    import re
    text = re.sub('<[^<]+?>', '', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def schedule_bulk_email(campaign):
    """
    Schedule email to be sent in background
    FIXED: Using sync=False to prevent signature errors
    """
    try:
        from django_q.tasks import async_task
        
        logger.info(f"Scheduling bulk email campaign {campaign.id}")
        
        # FIXED: Use sync=False to ensure proper task serialization
        task_id = async_task(
            'User.utils.send_bulk_email_task',
            campaign.id,
            timeout=7200,  # 2 hours max
            sync=False,  # CRITICAL: Prevent signature issues
            group=f'bulk_email_{campaign.id}'
        )
        
        logger.info(f"Campaign {campaign.id} queued with task_id: {task_id}")
        return task_id
        
    except Exception as e:
        logger.error(f"Failed to schedule campaign {campaign.id}: {str(e)}", exc_info=True)
        return None

def ensure_all_users_have_email_preferences():
    """
    Create email preferences for users who don't have them yet
    Run this once, or set it up as a scheduled task
    """
    from django.contrib.auth.models import User
    from User.models import Profile, EmailPreferences
    
    profiles_without_prefs = Profile.objects.filter(
        email_preferences__isnull=True
    )
    
    created_count = 0
    for profile in profiles_without_prefs:
        EmailPreferences.objects.create(
            profile=profile,
            receive_marketing=True,  # Default to opted-in
            receive_announcements=True,
            receive_notifications=True
        )
        created_count += 1
    
    return created_count

def get_email_preference_stats():
    """
    Get statistics about email preferences
    Useful for checking before sending campaigns
    """
    from User.models import EmailPreferences, Profile
    
    total_users = Profile.objects.count()
    
    # Users with preferences
    users_with_prefs = EmailPreferences.objects.count()
    
    # Users without preferences
    users_without_prefs = total_users - users_with_prefs
    
    # Opted in stats
    marketing_opted_in = EmailPreferences.objects.filter(receive_marketing=True).count()
    announcements_opted_in = EmailPreferences.objects.filter(receive_announcements=True).count()
    notifications_opted_in = EmailPreferences.objects.filter(receive_notifications=True).count()
    
    return {
        'total_users': total_users,
        'users_with_preferences': users_with_prefs,
        'users_without_preferences': users_without_prefs,
        'marketing_opted_in': marketing_opted_in,
        'announcements_opted_in': announcements_opted_in,
        'notifications_opted_in': notifications_opted_in,
    }