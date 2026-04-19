from django_q.tasks import async_task, result
from django_q.models import Schedule
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils.html import strip_tags
from django.utils import timezone
from django.db.models import Avg, Count, Sum, F, Q
from datetime import timedelta
import logging


logger = logging.getLogger(__name__)


def delete_expired_services():
    """Delete expired service listings - runs daily at 2 AM"""
    from .models import ServiceListing
    
    try:
        count = ServiceListing.delete_expired_services()
        logger.info(f"Deleted {count} expired services")
        return f"Deleted {count} expired services"
    except Exception as e:
        logger.error(f"Error deleting expired services: {str(e)}")
        raise


def update_service_boost_scores():
    """Update boost scores for all services - runs daily"""
    from .models import ServiceListing
    
    try:
        services = ServiceListing.objects.filter(is_active=True, is_suspended=False)
        updated = 0
        
        for service in services:
            old_score = service.boost_score
            new_score = service.calculate_boost_score()
            
            if old_score != new_score:
                ServiceListing.objects.filter(id=service.id).update(boost_score=new_score)
                updated += 1
        
        logger.info(f"Updated {updated} service boost scores")
        return f"Updated {updated} service boost scores"
        
    except Exception as e:
        logger.error(f"Error updating service boost scores: {str(e)}")
        raise


def send_inquiry_response_reminders():
    """Send reminders to providers about pending inquiries - runs daily"""
    from .models import ServiceInquiry
    
    try:
        # Find inquiries pending for 24+ hours
        one_day_ago = timezone.now() - timedelta(days=1)
        two_days_ago = timezone.now() - timedelta(days=2)
        
        pending_inquiries = ServiceInquiry.objects.filter(
            status='pending',
            created_at__range=[two_days_ago, one_day_ago]
        ).select_related('service__provider__user', 'client__user')
        
        sent_count = 0
        for inquiry in pending_inquiries:
            try:
                send_inquiry_reminder_email(inquiry.id)
                sent_count += 1
            except Exception as e:
                logger.error(f"Error sending inquiry reminder for {inquiry.id}: {str(e)}")
        
        logger.info(f"Sent {sent_count} inquiry response reminders")
        return f"Sent {sent_count} inquiry response reminders"
        
    except Exception as e:
        logger.error(f"Error sending inquiry reminders: {str(e)}")
        raise


def send_inquiry_reminder_email(inquiry_id):
    """Send reminder email for a specific inquiry"""
    from .models import ServiceInquiry
    
    try:
        inquiry = ServiceInquiry.objects.select_related(
            'service__provider__user', 'client__user'
        ).get(id=inquiry_id)
        
        context = {
            'provider': inquiry.service.provider.user,
            'inquiry': inquiry,
            'service': inquiry.service,
            'client': inquiry.client.user,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'inquiry_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/{inquiry.service.id}/",
            'dashboard_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/my-services/",
        }
        
        # Load email template
        html_message = render_to_string('emails/services/inquiry_reminder.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Inquiry Reminder: "{inquiry.service.title}"',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[inquiry.service.provider.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Inquiry reminder sent for {inquiry.service.title}"
        
    except Exception as e:
        logger.error(f"Error sending inquiry reminder email: {str(e)}")
        # Don't raise - this is not critical


def send_service_expiry_warnings():
    """Send warnings for services about to expire - runs daily"""
    from .models import ServiceListing
    
    try:
        # Find services expiring in 1, 3, or 7 days
        warning_services = ServiceListing.objects.filter(
            is_active=True,
            is_suspended=False,
            deletion_warning_sent=False,
            expiration_date__isnull=False
        )
        
        sent_count = 0
        for service in warning_services:
            days_remaining = service.days_until_expiration
            
            if days_remaining in [1, 3, 7]:
                try:
                    send_service_expiry_warning_email(service.id, days_remaining)
                    service.deletion_warning_sent = True
                    service.save(update_fields=['deletion_warning_sent'])
                    sent_count += 1
                except Exception as e:
                    logger.error(f"Error sending expiry warning for service {service.id}: {str(e)}")
        
        logger.info(f"Sent {sent_count} service expiry warnings")
        return f"Sent {sent_count} service expiry warnings"
        
    except Exception as e:
        logger.error(f"Error sending service expiry warnings: {str(e)}")
        raise


def send_service_expiry_warning_email(service_id, days_remaining):
    """Send expiry warning email for a specific service"""
    from .models import ServiceListing
    
    try:
        service = ServiceListing.objects.select_related('provider__user').get(id=service_id)
        
        context = {
            'provider': service.provider.user,
            'service': service,
            'days_remaining': days_remaining,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'service_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/{service.id}/",
            'update_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/{service.id}/edit/",
            'my_services_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/my-services/",
        }
        
        html_message = render_to_string('emails/services/service_expiring.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Service Expires in {days_remaining} Days - "{service.title}"',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[service.provider.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Expiry warning sent for {service.title}"
        
    except Exception as e:
        logger.error(f"Error sending service expiry warning email: {str(e)}")


def generate_service_performance_reports():
    """Generate performance reports for service providers - runs weekly"""
    from .models import ServiceListing, ServiceInquiry, ServiceReview
    
    try:
        # Get services with activity in the last week
        one_week_ago = timezone.now() - timedelta(days=7)
        
        active_services = ServiceListing.objects.filter(
            Q(inquiries__created_at__gte=one_week_ago) |
            Q(reviews__created_at__gte=one_week_ago) |
            Q(updated_at__gte=one_week_ago)
        ).distinct().select_related('provider__user')
        
        report_count = 0
        for service in active_services:
            try:
                # Generate performance data
                weekly_stats = {
                    'new_inquiries': service.inquiries.filter(created_at__gte=one_week_ago).count(),
                    'new_reviews': service.reviews.filter(created_at__gte=one_week_ago).count(),
                    'avg_rating': service.reviews.aggregate(avg=Avg('rating'))['avg'] or 0,
                    'total_views': service.view_count,
                    'response_rate': calculate_response_rate(service),
                    'total_inquiries': service.inquiries.count(),
                }
                
                # Send performance report (only for Pro users)
                try:
                    if service.provider.user.account.effective_status.tier_type == 'pro':
                        send_performance_report_email(service.id, weekly_stats)
                        report_count += 1
                except:
                    # Non-Pro users don't get detailed reports
                    pass
                    
            except Exception as e:
                logger.error(f"Error generating report for service {service.id}: {str(e)}")
        
        logger.info(f"Generated {report_count} service performance reports")
        return f"Generated {report_count} service performance reports"
        
    except Exception as e:
        logger.error(f"Error generating service performance reports: {str(e)}")
        raise


def calculate_response_rate(service):
    """Calculate response rate for a service"""
    total_inquiries = service.inquiries.count()
    if total_inquiries == 0:
        return 0
    
    responded_inquiries = service.inquiries.exclude(
        status='pending'
    ).count()
    
    return (responded_inquiries / total_inquiries) * 100


def send_performance_report_email(service_id, stats):
    """Send performance report email to service provider"""
    from .models import ServiceListing
    
    try:
        service = ServiceListing.objects.select_related('provider__user').get(id=service_id)
        
        context = {
            'provider': service.provider.user,
            'service': service,
            'stats': stats,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'service_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/{service.id}/",
            'my_services_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/my-services/",
        }
        
        html_message = render_to_string('emails/services/performance_report.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Weekly Performance Report: "{service.title}"',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[service.provider.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Performance report sent for {service.title}"
        
    except Exception as e:
        logger.error(f"Error sending performance report email: {str(e)}")


def cleanup_old_service_data():
    """Clean up old service data - runs weekly"""
    from .models import ServiceInquiry, ServiceConversation, ServiceMessage
    
    try:
        # Delete very old declined/cancelled inquiries (older than 6 months)
        six_months_ago = timezone.now() - timedelta(days=180)
        
        old_inquiries = ServiceInquiry.objects.filter(
            created_at__lt=six_months_ago,
            status__in=['declined', 'cancelled']
        )
        
        deleted_inquiry_count = old_inquiries.count()
        old_inquiries.delete()
        
        # Clean up old conversations with no activity (older than 1 year)
        one_year_ago = timezone.now() - timedelta(days=365)
        
        old_conversations = ServiceConversation.objects.filter(
            updated_at__lt=one_year_ago
        )
        
        deleted_conversation_count = old_conversations.count()
        old_conversations.delete()
        
        total_deleted = deleted_inquiry_count + deleted_conversation_count
        
        logger.info(f"Cleaned up {deleted_inquiry_count} old inquiries and {deleted_conversation_count} old conversations")
        return f"Cleaned up {total_deleted} old service records"
        
    except Exception as e:
        logger.error(f"Error cleaning up old service data: {str(e)}")
        raise


def send_service_optimization_tips():
    """Send optimization tips to service providers - runs monthly"""
    from .models import ServiceListing
    from django.db.models import Q
    
    try:
        # Find services that could use optimization
        one_month_ago = timezone.now() - timedelta(days=30)
        
        # Services with low inquiry rates
        low_activity_services = ServiceListing.objects.annotate(
            recent_inquiries=Count('inquiries', filter=Q(inquiries__created_at__gte=one_month_ago)),
            total_inquiries=Count('inquiries')
        ).filter(
            is_active=True,
            is_suspended=False,
            created_at__lt=one_month_ago,  # At least a month old
            recent_inquiries__lt=2  # Less than 2 inquiries in the last month
        ).select_related('provider__user')
        
        tip_count = 0
        for service in low_activity_services:
            try:
                # Generate optimization tips
                tips = generate_optimization_tips(service)
                
                # Send tips (only for Pro users or if they have 0 inquiries)
                try:
                    is_pro = service.provider.user.account.effective_status.tier_type == 'pro'
                    has_no_inquiries = service.total_inquiries == 0
                    
                    if is_pro or has_no_inquiries:
                        send_optimization_tips_email(service.id, tips)
                        tip_count += 1
                except:
                    pass
                    
            except Exception as e:
                logger.error(f"Error generating tips for service {service.id}: {str(e)}")
        
        logger.info(f"Sent {tip_count} service optimization tips")
        return f"Sent {tip_count} service optimization tips"
        
    except Exception as e:
        logger.error(f"Error sending optimization tips: {str(e)}")
        raise


def generate_optimization_tips(service):
    """Generate optimization tips for a service"""
    tips = []
    
    # Check if service has images
    if not service.images.exists():
        tips.append({
            'title': 'Add Images',
            'description': 'Add high-quality images to showcase your work and attract more clients.',
            'priority': 'High'
        })
    
    # Check description length
    if len(service.description) < 200:
        tips.append({
            'title': 'Expand Description',
            'description': 'Expand your service description to better explain what you offer and how you work.',
            'priority': 'Medium'
        })
    
    # Check if service has reviews
    if not service.reviews.exists():
        tips.append({
            'title': 'Get Reviews',
            'description': 'Encourage satisfied clients to leave reviews to build trust and credibility.',
            'priority': 'High'
        })
    
    # Check pricing strategy
    if service.pricing_type == 'negotiable' and not service.min_price:
        tips.append({
            'title': 'Set Pricing Range',
            'description': 'Consider setting a minimum price to attract serious clients and filter inquiries.',
            'priority': 'Medium'
        })
    
    # Check portfolio
    if not service.portfolio_url and not service.documents.exists():
        tips.append({
            'title': 'Add Portfolio',
            'description': 'Add portfolio samples or a portfolio link to showcase your previous work.',
            'priority': 'High'
        })
    
    # Check skills
    if not service.skills_offered:
        tips.append({
            'title': 'List Your Skills',
            'description': 'Add specific skills to help clients find you through search.',
            'priority': 'Medium'
        })
    
    # Check what you get section
    if not service.what_you_get:
        tips.append({
            'title': 'Clarify Deliverables',
            'description': 'Clearly explain what clients will receive to set proper expectations.',
            'priority': 'Medium'
        })
    
    return tips


def send_optimization_tips_email(service_id, tips):
    """Send optimization tips email to service provider"""
    from .models import ServiceListing
    
    try:
        service = ServiceListing.objects.select_related('provider__user').get(id=service_id)
        
        context = {
            'provider': service.provider.user,
            'service': service,
            'tips': tips,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'service_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/{service.id}/",
            'edit_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/{service.id}/edit/",
        }
        
        html_message = render_to_string('emails/services/optimization_tips.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Tips to Improve Your Service: "{service.title}"',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[service.provider.user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Optimization tips sent for {service.title}"
        
    except Exception as e:
        logger.error(f"Error sending optimization tips email: {str(e)}")


def generate_service_analytics():
    """Generate service analytics - runs daily"""
    from .models import ServiceListing, ServiceInquiry, ServiceReview, get_category_stats
    
    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        
        # Calculate daily statistics
        stats = {
            'new_services': ServiceListing.objects.filter(created_at__date=yesterday).count(),
            'new_inquiries': ServiceInquiry.objects.filter(created_at__date=yesterday).count(),
            'new_reviews': ServiceReview.objects.filter(created_at__date=yesterday).count(),
            'active_services': ServiceListing.objects.filter(
                is_active=True, 
                is_suspended=False
            ).count(),
            'total_service_views': ServiceListing.objects.aggregate(
                total=Sum('view_count')
            )['total'] or 0,
        }
        
        # Category performance
        category_stats = get_category_stats()
        
        logger.info(f"Generated service analytics: {stats}")
        
        # TODO: Store stats in database or send to analytics service
        # This could integrate with your existing analytics system
        
        return f"Generated service analytics: {stats}"
        
    except Exception as e:
        logger.error(f"Error generating service analytics: {str(e)}")
        raise


def send_new_service_notifications():
    """Send notifications about new services to interested users - runs hourly"""
    from .models import ServiceListing
    
    try:
        # Find services created in the last hour
        one_hour_ago = timezone.now() - timedelta(hours=1)
        new_services = ServiceListing.objects.filter(
            created_at__gte=one_hour_ago,
            is_active=True,
            is_suspended=False
        ).select_related('provider__user')
        
        notification_count = 0
        for service in new_services:
            # TODO: Implement logic to find interested users
            # This could be based on:
            # - Users who have saved similar services
            # - Users who have inquired about similar services
            # - Users with matching preferences in their profiles
            # - Pro users who want category notifications
            
            # For now, just log the new service
            logger.info(f"New service created: {service.title} by {service.provider.user.username}")
            notification_count += 1
        
        logger.info(f"Processed {notification_count} new service notifications")
        return f"Processed {notification_count} new service notifications"
        
    except Exception as e:
        logger.error(f"Error sending new service notifications: {str(e)}")
        raise


def update_service_rankings():
    """Update service rankings based on performance - runs daily"""
    from .models import ServiceListing
    
    try:
        services = ServiceListing.objects.filter(is_active=True, is_suspended=False)
        updated = 0
        
        for service in services:
            old_score = service.boost_score
            new_score = service.calculate_boost_score()
            
            if abs(old_score - new_score) > 0.1:  # Only update if significant change
                ServiceListing.objects.filter(id=service.id).update(boost_score=new_score)
                updated += 1
        
        logger.info(f"Updated rankings for {updated} services")
        return f"Updated rankings for {updated} services"
        
    except Exception as e:
        logger.error(f"Error updating service rankings: {str(e)}")
        raise


def send_provider_weekly_digest():
    """Send weekly digest to active service providers - runs weekly"""
    from .models import ServiceListing, ServiceInquiry
    from User.models import Profile
    
    try:
        # Find active service providers
        one_week_ago = timezone.now() - timedelta(days=7)
        
        active_providers = Profile.objects.filter(
            service_listings__isnull=False,
            service_listings__is_active=True,
            service_listings__is_suspended=False
        ).distinct()
        
        digest_count = 0
        for provider in active_providers:
            try:
                # Check if provider has Pro status for detailed digest
                is_pro = provider.user.account.effective_status.tier_type == 'pro'
                
                if is_pro:
                    # Generate weekly stats
                    provider_services = ServiceListing.objects.filter(provider=provider, is_active=True)
                    weekly_stats = {
                        'total_services': provider_services.count(),
                        'new_inquiries': ServiceInquiry.objects.filter(
                            service__provider=provider,
                            created_at__gte=one_week_ago
                        ).count(),
                        'total_views': provider_services.aggregate(total=Sum('view_count'))['total'] or 0,
                        'avg_rating': provider_services.aggregate(avg=Avg('reviews__rating'))['avg'] or 0,
                    }
                    
                    send_provider_digest_email(provider.user, weekly_stats)
                    digest_count += 1
                    
            except Exception as e:
                logger.error(f"Error generating digest for provider {provider.id}: {str(e)}")
        
        logger.info(f"Sent {digest_count} provider weekly digests")
        return f"Sent {digest_count} provider weekly digests"
        
    except Exception as e:
        logger.error(f"Error sending provider weekly digests: {str(e)}")
        raise


def send_provider_digest_email(user, stats):
    """Send weekly digest email to provider"""
    try:
        context = {
            'user': user,
            'stats': stats,
            'site_name': getattr(settings, 'SITE_NAME', 'OpenSell'),
            'dashboard_url': f"{getattr(settings, 'SITE_DOMAIN', '')}/services/my-services/",
        }
        
        html_message = render_to_string('emails/services/weekly_digest.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject=f'Your Weekly Service Digest - {getattr(settings, "SITE_NAME", "OpenSell")}',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f"Weekly digest sent to {user.username}"
        
    except Exception as e:
        logger.error(f"Error sending provider digest email: {str(e)}")


# Function to set up scheduled tasks (call this once during deployment)
def setup_service_tasks():
    """Set up scheduled tasks for services"""
    try:
        # Daily task to delete expired services (runs at 2 AM)
        Schedule.objects.get_or_create(
            name='delete_expired_services',
            defaults={
                'func': 'Services.tasks.delete_expired_services',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=2, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to update boost scores (runs at 3 AM)
        Schedule.objects.get_or_create(
            name='update_service_boost_scores',
            defaults={
                'func': 'Services.tasks.update_service_boost_scores',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=3, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to send inquiry reminders (runs at 10 AM)
        Schedule.objects.get_or_create(
            name='send_inquiry_response_reminders',
            defaults={
                'func': 'Services.tasks.send_inquiry_response_reminders',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to send expiry warnings (runs at 9 AM)
        Schedule.objects.get_or_create(
            name='send_service_expiry_warnings',
            defaults={
                'func': 'Services.tasks.send_service_expiry_warnings',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to generate performance reports (runs on Mondays at 9 AM)
        Schedule.objects.get_or_create(
            name='generate_service_performance_reports',
            defaults={
                'func': 'Services.tasks.generate_service_performance_reports',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=9, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to cleanup old data (runs on Sundays at 4 AM)
        Schedule.objects.get_or_create(
            name='cleanup_old_service_data',
            defaults={
                'func': 'Services.tasks.cleanup_old_service_data',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=4, minute=0, second=0, microsecond=0)
            }
        )
        
        # Monthly task to send optimization tips (runs on 1st of month at 8 AM)
        Schedule.objects.get_or_create(
            name='send_service_optimization_tips',
            defaults={
                'func': 'Services.tasks.send_service_optimization_tips',
                'schedule_type': Schedule.MONTHLY,
                'next_run': timezone.now().replace(hour=8, minute=0, second=0, microsecond=0)
            }
        )
        
        # Daily task to generate analytics (runs at 11:30 PM)
        Schedule.objects.get_or_create(
            name='generate_service_analytics',
            defaults={
                'func': 'Services.tasks.generate_service_analytics',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=23, minute=30, second=0, microsecond=0)
            }
        )
        
        # Daily task to update rankings (runs at 1 AM)
        Schedule.objects.get_or_create(
            name='update_service_rankings',
            defaults={
                'func': 'Services.tasks.update_service_rankings',
                'schedule_type': Schedule.DAILY,
                'next_run': timezone.now().replace(hour=1, minute=0, second=0, microsecond=0)
            }
        )
        
        # Weekly task to send provider digests (runs on Mondays at 7 AM)
        Schedule.objects.get_or_create(
            name='send_provider_weekly_digest',
            defaults={
                'func': 'Services.tasks.send_provider_weekly_digest',
                'schedule_type': Schedule.WEEKLY,
                'next_run': timezone.now().replace(hour=7, minute=0, second=0, microsecond=0)
            }
        )
        
        # Hourly task to send new service notifications
        Schedule.objects.get_or_create(
            name='send_new_service_notifications',
            defaults={
                'func': 'Services.tasks.send_new_service_notifications',
                'schedule_type': Schedule.HOURLY,
                'next_run': timezone.now().replace(minute=30, second=0, microsecond=0)
            }
        )
        
        logger.info("Service scheduled tasks set up successfully")
        
    except Exception as e:
        logger.error(f"Error setting up service tasks: {str(e)}")
        raise


# Manual task runners (for testing or one-time execution)
def run_all_service_maintenance():
    """Run all maintenance tasks manually"""
    results = []
    
    try:
        results.append(delete_expired_services())
    except Exception as e:
        results.append(f"Error in delete_expired_services: {e}")
    
    try:
        results.append(update_service_boost_scores())
    except Exception as e:
        results.append(f"Error in update_service_boost_scores: {e}")
    
    try:
        results.append(cleanup_old_service_data())
    except Exception as e:
        results.append(f"Error in cleanup_old_service_data: {e}")
    
    try:
        results.append(update_service_rankings())
    except Exception as e:
        results.append(f"Error in update_service_rankings: {e}")
    
    return results


def force_send_all_reminders():
    """Force send all pending reminders (for testing)"""
    results = []
    
    try:
        results.append(send_inquiry_response_reminders())
    except Exception as e:
        results.append(f"Error in send_inquiry_response_reminders: {e}")
    
    try:
        results.append(send_service_expiry_warnings())
    except Exception as e:
        results.append(f"Error in send_service_expiry_warnings: {e}")
    
    return results