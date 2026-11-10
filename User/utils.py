from django.core.mail import send_mail
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.template.loader import render_to_string
import datetime
import hashlib
import html
import re
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
    """Kept so old callers and queued tasks keep working: sends today's batch for one campaign."""
    return send_bulk_email_batch(email_id)


# --- daily-cap sending ------------------------------------------------------------------------------------------
# Provider quota (Resend transactional plan): 100 emails per day, shared by everything. Bulk campaigns may use at most
# BULK_EMAIL_DAILY_CAP of them (default 75); the rest is kept for OTP, welcome and verification emails. A campaign is
# sent over several days: each batch emails the next people who are not in BulkEmailRecipient yet, and stops at the cap.
BULK_LOCK_KEY = 'bulk_email_batch_lock'
BULK_LOCK_SECONDS = 15 * 60          # same 15 minutes as the send lock in the admin view
BULK_MAX_SECONDS = 480               # stop a batch after 8 minutes, under the 600 s django-q task timeout
BULK_STALE_CLAIM = datetime.timedelta(hours=2)
BULK_BREAKER = 3                     # this many failures in a row means the provider is down: stop, do not burn attempts

BULK_VAR_RE = re.compile(r'\{\{(first_name|username|site_name|site_url)\}\}')   # no spaces inside the braces
BULK_SUBJECT_RE = re.compile(r'\{\{first_name\}\}')


def bulk_daily_cap():
    return max(0, int(getattr(settings, 'BULK_EMAIL_DAILY_CAP', 75)))


def provider_daily_limit():
    return max(0, int(getattr(settings, 'EMAIL_DAILY_LIMIT', 100)))


def _utc_day_start():
    return timezone.now().astimezone(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def bulk_budget_today():
    """
    How many more bulk emails may go out today (UTC day, which is when the provider's daily quota resets).
    left = min(cap - bulk_used, limit - bulk_used - max(reserve, other_used)), reserve = limit - cap.
    Other emails (OTP, welcome, ...) come from the counter in User/email_backend.py: counter total minus bulk sent.
    If the counter is not installed it reads 0, and the result is the plain cap.
    """
    from django.db.models import Q
    from User.models import BulkEmailRecipient, EmailSendCounter
    start = _utc_day_start()
    cap, limit = bulk_daily_cap(), provider_daily_limit()
    sent = BulkEmailRecipient.objects.filter(status='sent', sent_at__gte=start).count()
    in_flight = BulkEmailRecipient.objects.filter(status='sending', updated_at__gte=start).count()
    total_today = EmailSendCounter.objects.filter(day=start.date()).values_list('total', flat=True).first() or 0
    other = max(0, total_today - sent)
    reserve = max(0, limit - cap)
    used = sent + in_flight
    left = max(0, min(cap - used, limit - used - max(reserve, other)))
    return {'cap': cap, 'limit': limit, 'bulk_used': sent, 'in_flight': in_flight, 'other_used': other,
            'reserve': reserve, 'left': left, 'counter_installed': total_today > 0}


def bulk_send_plan(remaining):
    """Plain numbers for the confirm page: how many go today and about how many days it takes."""
    b = bulk_budget_today()
    today = min(remaining, b['left'])
    rest = remaining - today
    per_day = max(1, b['cap'])
    days = (1 if today else 0) + -(-rest // per_day)
    return {'today': today, 'days': days, 'starts_today': today > 0, 'per_day': b['cap']}


def _fill(template, values, escape):
    def repl(m):
        v = values[m.group(1)]
        return html.escape(v) if escape else v
    return BULK_VAR_RE.sub(repl, template or '')      # one pass, so a value is never expanded again


def send_single_email(user, campaign):
    """Send one campaign email. Raises on any problem, so the batch can log the failure for that person."""
    from django.core.mail import EmailMultiAlternatives

    try:
        user.profile.email_preferences
    except Exception:
        raise ValueError('no email preferences')
    if not user.email:
        raise ValueError('no email address')

    first_name = ' '.join((user.first_name or user.username).split())    # one line: it also goes in the subject
    values = {'first_name': first_name, 'username': user.username,
              'site_name': settings.SITE_NAME, 'site_url': settings.SITE_URL}

    subject = BULK_SUBJECT_RE.sub(lambda m: first_name, campaign.subject)        # only first_name, plain text
    html_content = wrap_email_simple(_fill(campaign.message, values, escape=True), user)
    plain_content = html.unescape(strip_html_simple(_fill(campaign.message, values, escape=False)))

    email = EmailMultiAlternatives(subject=subject, body=plain_content, from_email=settings.DEFAULT_FROM_EMAIL,
                                   to=[user.email])
    email.attach_alternative(html_content, "text/html")
    email.send(fail_silently=False)


def _claim(campaign, user_id):
    """Take the right to email this person. Returns the log row, or None if someone else has it or it is done."""
    from django.db import transaction
    from django.db.models import F
    from User.models import BulkEmailRecipient
    with transaction.atomic():
        log, created = BulkEmailRecipient.objects.get_or_create(
            campaign=campaign, user_id=user_id, defaults={'status': 'sending', 'attempts': 1})
    if created:
        return log
    taken = BulkEmailRecipient.objects.filter(
        pk=log.pk, status='failed', attempts__lt=campaign.MAX_ATTEMPTS
    ).update(status='sending', attempts=F('attempts') + 1, error='')
    return log if taken else None


def _next_recipient_ids(campaign, limit):
    """People never tried first, then earlier failures that still have attempts left. Each is returned once."""
    failed_ids = list(campaign.recipient_logs.filter(status='failed', attempts__lt=campaign.MAX_ATTEMPTS)
                      .values_list('user_id', flat=True))
    base = campaign.sendable_recipients()
    ids = list(base.exclude(id__in=failed_ids).order_by('id').values_list('id', flat=True)[:limit])
    if len(ids) < limit and failed_ids:
        ids += list(base.filter(id__in=failed_ids).order_by('id').values_list('id', flat=True)[:limit - len(ids)])
    return ids


def _release_stale_claims():
    """A claim left in 'sending' for hours means a worker died mid-send. We cannot know whether the email left, and
    sending twice is worse than missing one, so it is marked failed with no automatic retry. Staff can retry it."""
    from User.models import BulkEmail, BulkEmailRecipient
    return BulkEmailRecipient.objects.filter(
        status='sending', updated_at__lt=timezone.now() - BULK_STALE_CLAIM
    ).update(status='failed', attempts=BulkEmail.MAX_ATTEMPTS, error='Interrupted, delivery unknown')


def _settle(campaign_id):
    """After a batch: sent when nobody is left to try, otherwise in progress."""
    from User.models import BulkEmail
    c = BulkEmail.objects.get(pk=campaign_id)
    done = not c.sendable_recipients().exists() and not c.recipient_logs.filter(status='sending').exists()
    fields = {'total_sent': c.recipient_logs.filter(status='sent').count()}
    if done:
        fields.update(status='sent', sent_at=c.sent_at or timezone.now())
    else:
        fields.update(status='partial')
    BulkEmail.objects.filter(pk=campaign_id, status='sending').update(**fields)
    BulkEmail.objects.filter(pk=campaign_id).exclude(status='sending').update(total_sent=fields['total_sent'])


def send_bulk_email_batch(campaign_id=None, max_emails=None):
    """
    Send today's batch. Called by the django-q schedule (no arguments), by the admin button and by the send view.
    campaign_id: only that campaign; None: every campaign in progress, oldest first.
    max_emails: extra limit, used for the in-request fallback when the queue is down.
    Returns {'success', 'sent', 'failed', 'stopped'}; stopped is '', 'budget', 'time', 'provider' or 'locked'.
    """
    from django.core.cache import cache
    if not cache.add(BULK_LOCK_KEY, 1, BULK_LOCK_SECONDS):
        logger.info('Bulk batch skipped: another batch is running')
        return {'success': True, 'sent': 0, 'failed': 0, 'stopped': 'locked'}
    try:
        return _run_batch(campaign_id, max_emails)
    except Exception as e:
        logger.error('Bulk batch failed: %s', e, exc_info=True)
        return {'success': False, 'sent': 0, 'failed': 0, 'stopped': '', 'error': str(e)}
    finally:
        cache.delete(BULK_LOCK_KEY)


def _run_batch(campaign_id, max_emails):
    from django.contrib.auth.models import User
    from django.db.models import F
    from User.models import BulkEmail, BulkEmailRecipient

    _release_stale_claims()
    left = bulk_budget_today()['left']
    if max_emails is not None:
        left = min(left, max_emails)
    deadline = time.monotonic() + BULK_MAX_SECONDS

    campaigns = BulkEmail.objects.filter(status__in=('sending', 'partial')).order_by('created_at')
    if campaign_id is not None:
        campaigns = campaigns.filter(pk=campaign_id)

    sent = failed = 0
    streak = []
    stopped = '' if left > 0 else 'budget'

    for campaign in list(campaigns):
        BulkEmail.objects.filter(pk=campaign.pk, status__in=('sending', 'partial')).update(status='sending')
        try:
            if not stopped:
                for uid in _next_recipient_ids(campaign, left):
                    if time.monotonic() > deadline:
                        stopped = 'time'
                        break
                    user = User.objects.filter(pk=uid, is_active=True).first()
                    log = _claim(campaign, uid) if user else None
                    if log is None:
                        continue
                    try:
                        send_single_email(user, campaign)
                    except Exception as e:
                        BulkEmailRecipient.objects.filter(pk=log.pk).update(status='failed', error=str(e)[:255])
                        failed += 1
                        streak.append(log.pk)
                        logger.error('Campaign %s: failed for user %s: %s', campaign.pk, uid, e)
                        if len(streak) >= BULK_BREAKER:
                            # Looks like the provider, not these people: give the attempts back and stop for today.
                            BulkEmailRecipient.objects.filter(pk__in=streak).update(attempts=F('attempts') - 1)
                            stopped = 'provider'
                            break
                    else:
                        BulkEmailRecipient.objects.filter(pk=log.pk).update(
                            status='sent', sent_at=timezone.now(), error='')
                        sent += 1
                        left -= 1
                        streak = []
                        if left <= 0:
                            stopped = 'budget'
                            break
        finally:
            _settle(campaign.pk)

    logger.info('Bulk batch done: %s sent, %s failed, stopped=%s', sent, failed, stopped or 'none')
    return {'success': True, 'sent': sent, 'failed': failed, 'stopped': stopped}

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
    """Queue a batch for one campaign (the daily schedule continues it on the following days)."""
    try:
        from django_q.tasks import async_task

        logger.info(f"Scheduling bulk email campaign {campaign.id}")
        task_id = async_task(
            'User.utils.send_bulk_email_batch',
            campaign.id,
            timeout=600,  # must stay below Q_CLUSTER['retry']
            sync=False,
            group=f'bulk_email_{campaign.id}'
        )
        logger.info(f"Campaign {campaign.id} queued with task_id: {task_id}")
        return task_id

    except Exception as e:
        logger.error(f"Failed to schedule campaign {campaign.id}: {str(e)}", exc_info=True)
        return None

def ensure_bulk_email_batch_schedule(hour_utc=8):
    """
    Create the daily django-q Schedule that continues campaigns (safe to run twice).
    Run once:  python manage.py shell -c "from User.utils import ensure_bulk_email_batch_schedule as e; print(e())"
    """
    from django_q.models import Schedule

    existing = Schedule.objects.filter(func='User.utils.send_bulk_email_batch').first()
    if existing:
        return existing
    now = timezone.now()
    first = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
    if first <= now:
        first += datetime.timedelta(days=1)
    return Schedule.objects.create(
        func='User.utils.send_bulk_email_batch', name='Bulk email daily batch',
        schedule_type=Schedule.DAILY, repeats=-1, next_run=first)

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

def get_client_ip(request):
    """Real visitor IP behind Cloudflare. Locally (DEBUG) uses REMOTE_ADDR."""
    if not settings.DEBUG:
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip.strip()
    return request.META.get('REMOTE_ADDR')