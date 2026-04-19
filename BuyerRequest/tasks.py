from django_q.tasks import async_task, result
from django_q.models import Schedule
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
from django.db.models import Count, Avg, Sum, F, Q
import logging


logger = logging.getLogger(__name__)


def delete_expired_requests():
    """Delete expired buyer requests - runs daily (following existing pattern)"""
    from .models import BuyerRequest
    
    try:
        count = BuyerRequest.delete_expired_requests()
        logger.info(f"Deleted {count} expired buyer requests")
        return f"Deleted {count} expired buyer requests"
    except Exception as e:
        logger.error(f"Error deleting expired buyer requests: {str(e)}")
        raise


def mark_expired_requests():
    """Mark expired requests as expired - runs daily"""
    from .models import BuyerRequest
    from .signals import mark_expired_requests as mark_expired
    
    try:
        count = mark_expired()
        logger.info(f"Marked {count} requests as expired")
        return f"Marked {count} requests as expired"
    except Exception as e:
        logger.error(f"Error marking expired requests: {str(e)}")
        raise


def send_expiring_request_warnings():
    """Send warnings for expiring requests - runs daily"""
    from .models import BuyerRequest
    from .signals import check_expiring_requests
    
    try:
        check_expiring_requests()
        logger.info("Sent expiring request warnings")
        return "Sent expiring request warnings"
    except Exception as e:
        logger.error(f"Error sending expiring request warnings: {str(e)}")
        raise


def send_request_expiry_warning(request_id, days_remaining):
    """Send expiry warning for a specific request"""
    from .models import BuyerRequest
    
    try:
        request = BuyerRequest.objects.select_related('buyer__user').get(id=request_id)
        
        context = {
            'user': request.buyer.user,
            'request': request,
            'days_remaining': days_remaining,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'update_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/buyer-requests/{request.id}/edit/",
            'bump_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/buyer-requests/{request.id}/bump/",
        }
        
        # Load email template (following existing pattern)
        html_message = render_to_string('emails/request_expiring.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Request "{request.title}" Expires in {days_remaining} Days',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.buyer.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Expiry warning sent for {request.title}"
        
    except Exception as e:
        logger.error(f"Error sending request expiry warning: {str(e)}")
        # Don't raise - this is not critical


def cleanup_old_request_access_records():
    """Clean up old request access records - runs weekly"""
    from .models import RequestAccess
    from datetime import timedelta
    
    try:
        # Delete access records older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)
        
        deleted_count, _ = RequestAccess.objects.filter(
            accessed_at__lt=cutoff_date
        ).delete()
        
        logger.info(f"Cleaned up {deleted_count} old request access records")
        return f"Cleaned up {deleted_count} old request access records"
        
    except Exception as e:
        logger.error(f"Error cleaning up old request access records: {str(e)}")
        raise


def cleanup_old_conversations():
    """Clean up old conversations with no recent activity - runs weekly"""
    from .models import RequestConversation
    from datetime import timedelta
    
    try:
        # Delete conversations older than 6 months with no recent messages
        cutoff_date = timezone.now() - timedelta(days=180)
        
        old_conversations = RequestConversation.objects.filter(
            updated_at__lt=cutoff_date,
            messages__timestamp__lt=cutoff_date
        ).distinct()
        
        deleted_count = 0
        for conversation in old_conversations:
            conversation.delete()
            deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old conversations")
        return f"Cleaned up {deleted_count} old conversations"
        
    except Exception as e:
        logger.error(f"Error cleaning up old conversations: {str(e)}")
        raise


def generate_daily_request_stats():
    """Generate daily statistics for requests - runs daily"""
    from .models import BuyerRequest, SellerResponse
    from datetime import date
    
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Calculate statistics
        stats = {
            'new_requests': BuyerRequest.objects.filter(created_at__date=yesterday).count(),
            'new_responses': SellerResponse.objects.filter(created_at__date=yesterday).count(),
            'active_requests': BuyerRequest.objects.filter(
                status='active', 
                is_suspended=False,
                expires_at__gt=timezone.now()
            ).count(),
            'fulfilled_requests': BuyerRequest.objects.filter(
                status='fulfilled',
                updated_at__date=yesterday
            ).count(),
            'total_views': BuyerRequest.objects.filter(
                created_at__date=yesterday
            ).aggregate(total=Sum('view_count'))['total'] or 0,
        }
        
        logger.info(f"Daily stats generated: {stats}")
        
        # TODO: Store stats in database or send to analytics service
        # This could integrate with your existing analytics system
        
        return f"Generated daily stats: {stats}"
        
    except Exception as e:
        logger.error(f"Error generating daily request stats: {str(e)}")
        raise


def send_new_request_notifications():
    """Send notifications about new requests to interested sellers - runs hourly"""
    from .models import BuyerRequest
    from .signals import notify_interested_sellers
    
    try:
        notification_count = notify_interested_sellers()
        logger.info(f"Sent {notification_count} new request notifications")
        return f"Sent {notification_count} new request notifications"
        
    except Exception as e:
        logger.error(f"Error sending new request notifications: {str(e)}")
        raise


def update_request_boost_scores():
    """Update boost scores for all active requests - runs daily"""
    from .models import BuyerRequest
    
    try:
        active_requests = BuyerRequest.objects.filter(
            status='active',
            is_suspended=False
        )
        
        updated_count = 0
        for request in active_requests:
            old_score = request.boost_score
            new_score = request.calculate_boost_score()
            
            if old_score != new_score:
                BuyerRequest.objects.filter(id=request.id).update(boost_score=new_score)
                updated_count += 1
        
        logger.info(f"Updated boost scores for {updated_count} requests")
        return f"Updated boost scores for {updated_count} requests"
        
    except Exception as e:
        logger.error(f"Error updating request boost scores: {str(e)}")
        raise


def send_weekly_request_digest():
    """Send weekly digest to Pro users about request activity - runs weekly"""
    from .models import BuyerRequest, SellerResponse
    from User.models import Profile
    from datetime import timedelta
    
    try:
        # Get Pro users
        pro_users = Profile.objects.filter(
            user__account__effective_status__tier_type='pro'
        ).select_related('user')
        
        one_week_ago = timezone.now() - timedelta(days=7)
        
        digest_count = 0
        for profile in pro_users:
            try:
                # Get user's activity
                user_requests = BuyerRequest.objects.filter(
                    buyer=profile,
                    created_at__gte=one_week_ago
                )
                
                user_responses = SellerResponse.objects.filter(
                    seller=profile,
                    created_at__gte=one_week_ago
                )
                
                # Only send digest if there's activity
                if user_requests.exists() or user_responses.exists():
                    send_weekly_digest_email(profile.user.id)
                    digest_count += 1
                    
            except Exception as e:
                logger.error(f"Error sending digest to user {profile.user.username}: {str(e)}")
        
        logger.info(f"Sent {digest_count} weekly digests")
        return f"Sent {digest_count} weekly digests"
        
    except Exception as e:
        logger.error(f"Error sending weekly request digests: {str(e)}")
        raise


def send_weekly_digest_email(user_id):
    """Send weekly digest email to a specific user"""
    from django.contrib.auth.models import User
    from .models import BuyerRequest, SellerResponse
    from datetime import timedelta
    
    try:
        user = User.objects.select_related('profile').get(id=user_id)
        one_week_ago = timezone.now() - timedelta(days=7)
        
        # Get user's stats
        user_requests = BuyerRequest.objects.filter(
            buyer=user.profile,
            created_at__gte=one_week_ago
        )
        
        user_responses = SellerResponse.objects.filter(
            seller=user.profile,
            created_at__gte=one_week_ago
        )
        
        # Get responses to user's requests
        responses_received = SellerResponse.objects.filter(
            buyer_request__buyer=user.profile,
            created_at__gte=one_week_ago
        )
        
        context = {
            'user': user,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'requests_posted': user_requests.count(),
            'responses_sent': user_responses.count(),
            'responses_received': responses_received.count(),
            'total_views': user_requests.aggregate(total=Sum('view_count'))['total'] or 0,
            'recent_requests': user_requests[:5],
            'recent_responses': responses_received[:5],
        }
        
        html_message = render_to_string('emails/weekly_request_digest.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Weekly Request Activity - {getattr(settings, "SITE_NAME", "OpenSell")}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        return f"Weekly digest sent to {user.username}"
        
    except Exception as e:
        logger.error(f"Error sending weekly digest email: {str(e)}")


def cleanup_orphaned_images():
    """Clean up orphaned request images - runs weekly"""
    from .models import BuyerRequestImage
    import os
    
    try:
        orphaned_count = 0
        
        for image in BuyerRequestImage.objects.all():
            try:
                if not os.path.exists(image.image.path):
                    image.delete()
                    orphaned_count += 1
            except Exception:
                # Image file doesn't exist, delete the record
                image.delete()
                orphaned_count += 1
        
        logger.info(f"Cleaned up {orphaned_count} orphaned images")
        return f"Cleaned up {orphaned_count} orphaned images"
        
    except Exception as e:
        logger.error(f"Error cleaning up orphaned images: {str(e)}")
        raise


def generate_weekly_performance_reports():
    """Generate weekly performance reports for Pro users - runs weekly"""
    from .models import BuyerRequest, SellerResponse
    from User.models import Profile
    from datetime import timedelta
    
    try:
        # Get Pro users who have been active
        one_week_ago = timezone.now() - timedelta(days=7)
        
        active_pro_users = Profile.objects.filter(
            user__account__effective_status__tier_type='pro'
        ).filter(
            Q(buyer_requests__created_at__gte=one_week_ago) |
            Q(seller_responses__created_at__gte=one_week_ago)
        ).distinct().select_related('user')
        
        report_count = 0
        for profile in active_pro_users:
            try:
                # Generate performance data
                weekly_stats = {
                    'requests_posted': profile.buyer_requests.filter(created_at__gte=one_week_ago).count(),
                    'responses_sent': profile.seller_responses.filter(created_at__gte=one_week_ago).count(),
                    'responses_received': SellerResponse.objects.filter(
                        buyer_request__buyer=profile,
                        created_at__gte=one_week_ago
                    ).count(),
                    'total_views': profile.buyer_requests.filter(
                        created_at__gte=one_week_ago
                    ).aggregate(total=Sum('view_count'))['total'] or 0,
                    'avg_response_score': profile.seller_responses.filter(
                        created_at__gte=one_week_ago
                    ).aggregate(avg=Avg('response_score'))['avg'] or 0,
                }
                
                # Send performance report
                send_performance_report_email(profile.user.id, weekly_stats)
                report_count += 1
                    
            except Exception as e:
                logger.error(f"Error generating report for user {profile.user.username}: {str(e)}")
        
        logger.info(f"Generated {report_count} performance reports")
        return f"Generated {report_count} performance reports"
        
    except Exception as e:
        logger.error(f"Error generating weekly performance reports: {str(e)}")
        raise


def send_performance_report_email(user_id, stats):
    """Send performance report email to a specific user"""
    from django.contrib.auth.models import User
    
    try:
        user = User.objects.get(id=user_id)
        
        context = {
            'user': user,
            'stats': stats,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'site_domain': getattr(settings, 'SITE_DOMAIN', ''),
        }
        
        html_message = render_to_string('emails/weekly_performance_report.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Weekly Performance Report - {getattr(settings, "SITE_NAME", "OpenSell")}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=True,
        )
        
        return f"Performance report sent to {user.username}"
        
    except Exception as e:
        logger.error(f"Error sending performance report email: {str(e)}")


# Function to set up scheduled tasks (call this once during deployment)
def setup_buyer_request_tasks():
    """Set up scheduled tasks for buyer requests"""
    try:
        # Daily task to delete expired requests (runs at 1 AM)
        Schedule.objects.get_or_create(
            name='delete_expired_requests',
            defaults={
                'func': 'BuyerRequest.tasks.delete_expired_requests',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=1, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to mark expired requests (runs at 12:30 AM)
        Schedule.objects.get_or_create(
            name='mark_expired_requests',
            defaults={
                'func': 'BuyerRequest.tasks.mark_expired_requests',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=0, minute=30, second=0, microsecond=0)
            }
        )
        
        # Daily task to send expiry warnings (runs at 9 AM)
        Schedule.objects.get_or_create(
            name='send_expiring_request_warnings',
            defaults={
                'func': 'BuyerRequest.tasks.send_expiring_request_warnings',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to update boost scores (runs at 3 AM)
        Schedule.objects.get_or_create(
            name='update_request_boost_scores',
            defaults={
                'func': 'BuyerRequest.tasks.update_request_boost_scores',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=3, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to generate stats (runs at 2 AM)
        Schedule.objects.get_or_create(
            name='generate_daily_request_stats',
            defaults={
                'func': 'BuyerRequest.tasks.generate_daily_request_stats',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=2, minute=0, second=0, microsecond=0)
            }
        )
        
        # Hourly task to send new request notifications
        Schedule.objects.get_or_create(
            name='send_new_request_notifications',
            defaults={
                'func': 'BuyerRequest.tasks.send_new_request_notifications',
                'schedule_type': Schedule.HOURLY,
                'next_run': timezone.now().replace(minute=15, second=0, microsecond=0)
            }
        )
        
        # Weekly task to cleanup old access records (runs on Sundays at 2 AM)
        Schedule.objects.get_or_create(
            name='cleanup_old_request_access_records',
            defaults={
                'func': 'BuyerRequest.tasks.cleanup_old_request_access_records',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=2, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to cleanup old conversations (runs on Sundays at 3 AM)
        Schedule.objects.get_or_create(
            name='cleanup_old_conversations',
            defaults={
                'func': 'BuyerRequest.tasks.cleanup_old_conversations',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=3, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to cleanup orphaned images (runs on Sundays at 4 AM)
        Schedule.objects.get_or_create(
            name='cleanup_orphaned_images',
            defaults={
                'func': 'BuyerRequest.tasks.cleanup_orphaned_images',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=4, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to send digest emails (runs on Mondays at 8 AM)
        Schedule.objects.get_or_create(
            name='send_weekly_request_digest',
            defaults={
                'func': 'BuyerRequest.tasks.send_weekly_request_digest',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to generate performance reports (runs on Mondays at 10 AM)
        Schedule.objects.get_or_create(
            name='generate_weekly_performance_reports',
            defaults={
                'func': 'BuyerRequest.tasks.generate_weekly_performance_reports',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
            }
        )
        
        logger.info("Buyer request scheduled tasks set up successfully")
        
    except Exception as e:
        logger.error(f"Error setting up buyer request tasks: {str(e)}")
        raise