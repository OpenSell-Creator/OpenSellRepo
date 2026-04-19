from django.db.models.signals import post_save, pre_delete, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import F
from datetime import timedelta
import logging
from .models import (
    ServiceListing, ServiceInquiry, ServiceImage, ServiceDocument, 
    ServiceReview
)

logger = logging.getLogger(__name__)

def safe_create_notification(user, title, message, category=None, priority=None, 
                            content_object=None, action_url=None, action_text=None):
    """Safely create notification - handles missing Notifications app"""
    try:
        from Notifications.models import create_notification, NotificationCategory, NotificationPriority
        # Use the actual notification system if available
        return create_notification(
            user=user,
            title=title,
            message=message,
            category=getattr(NotificationCategory, category, None) if category else None,
            priority=getattr(NotificationPriority, priority, None) if priority else None,
            content_object=content_object,
            action_url=action_url,
            action_text=action_text
        )
    except ImportError:
        # Fallback: Log or store in simple model
        print(f"Notification: {user.username} - {title}: {message}")
        return True
    except Exception as e:
        # Handle any other notification errors
        print(f"Notification error: {e}")
        return False

@receiver(post_save, sender=ServiceInquiry)
def handle_inquiry_created(sender, instance, created, **kwargs):
    """Handle actions when a new inquiry is created - IMPROVED"""
    if created:
        try:
            # Update inquiry count on service listing
            ServiceListing.objects.filter(id=instance.service.id).update(
                inquiry_count=F('inquiry_count') + 1
            )
            
            # Create notification for service provider
            try:
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=instance.service.provider.user,
                    title="New Service Inquiry",
                    message=f'{instance.client.user.username} is interested in your service "{instance.service.title}"',
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=instance,
                    action_url=instance.service.get_absolute_url(),
                    action_text="View Inquiry"
                )
                
                # Send email notification
                from .utils import send_service_notification_email
                send_service_notification_email(
                    instance.service, 
                    'new_inquiry', 
                    {'inquiry': instance, 'client': instance.client.user}
                )
                
            except ImportError:
                logger.warning("Notifications app not available")
            except Exception as e:
                logger.error(f"Error creating inquiry notification: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error handling inquiry creation: {str(e)}")


@receiver(post_delete, sender=ServiceInquiry)
def handle_inquiry_deleted(sender, instance, **kwargs):
    """Handle actions when an inquiry is deleted"""
    try:
        # Decrease inquiry count on service listing
        ServiceListing.objects.filter(id=instance.service.id).update(
            inquiry_count=F('inquiry_count') - 1
        )
    except Exception as e:
        logger.error(f"Error handling inquiry deletion: {str(e)}")



@receiver(post_save, sender=ServiceReview)
def handle_review_created(sender, instance, created, **kwargs):
    """Handle actions when a new review is created - IMPROVED"""
    if created:
        try:
            # Create notification for service provider
            try:
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=instance.service.provider.user,
                    title="New Service Review",
                    message=f'{instance.reviewer.username} left a {instance.rating}-star review for "{instance.service.title}"',
                    category=NotificationCategory.REVIEWS,
                    priority=NotificationPriority.MEDIUM,
                    content_object=instance,
                    action_url=instance.service.get_absolute_url(),
                    action_text="View Review"
                )
                
                # Send email notification
                from .utils import send_service_notification_email
                send_service_notification_email(
                    instance.service, 
                    'new_review', 
                    {'review': instance, 'reviewer': instance.reviewer}
                )
                
            except ImportError:
                logger.warning("Notifications app not available")
            except Exception as e:
                logger.error(f"Error creating review notification: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error handling review creation: {str(e)}")



@receiver(pre_save, sender=ServiceListing)
def update_service_boost_score(sender, instance, **kwargs):
    """Update boost score when service is saved"""
    # Calculate and update boost score
    calculated_score = instance.calculate_boost_score()
    instance.boost_score = calculated_score



@receiver(post_save, sender=ServiceListing)
def handle_service_status_change(sender, instance, created, **kwargs):
    """Handle service status changes and creation - IMPROVED"""
    try:
        if created:
            # Update provider's total services count
            from User.models import Profile
            Profile.objects.filter(id=instance.provider.id).update(
                total_services_listed=F('total_services_listed') + 1
            )
            
            # Create notification for new service
            try:
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=instance.provider.user,
                    title="Service Listed Successfully",
                    message=f'Your service "{instance.title}" has been published and is now visible to clients.',
                    category=NotificationCategory.SYSTEM,
                    priority=NotificationPriority.LOW,
                    content_object=instance,
                    action_url=instance.get_absolute_url(),
                    action_text="View Service"
                )
            except ImportError:
                logger.warning("Notifications app not available")
            except Exception as e:
                logger.error(f"Error creating service creation notification: {str(e)}")
        
        else:
            # Check if service was suspended
            if instance.is_suspended:
                try:
                    from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                    create_notification(
                        user=instance.provider.user,
                        title="Service Suspended",
                        message=f'Your service "{instance.title}" has been suspended. Please check your email for details.',
                        category=NotificationCategory.ALERTS,
                        priority=NotificationPriority.HIGH,
                        content_object=instance,
                        action_url=instance.get_absolute_url(),
                        action_text="View Service"
                    )
                except ImportError:
                    logger.warning("Notifications app not available")
                except Exception as e:
                    logger.error(f"Error creating suspension notification: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error handling service status change: {str(e)}")



@receiver(pre_save, sender=ServiceListing)
def check_service_expiration(sender, instance, **kwargs):
    """Check service expiration and send warnings - IMPROVED"""
    try:
        if not hasattr(instance, '_original_deletion_warning_sent'):
            try:
                original = ServiceListing.objects.get(pk=instance.pk)
                instance._original_deletion_warning_sent = original.deletion_warning_sent
            except ServiceListing.DoesNotExist:
                instance._original_deletion_warning_sent = False
        else:
            instance._original_deletion_warning_sent = instance.deletion_warning_sent

        if instance.expiration_date and instance.id:
            days_left = instance.days_until_expiration
            
            # Only send notification if conditions are met
            if (days_left in [1, 3, 7] and not instance._original_deletion_warning_sent):
                try:
                    from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                    create_notification(
                        user=instance.provider.user,
                        title="Service Expiring Soon",
                        message=f'Your service "{instance.title}" will expire in {days_left} day(s). Renew it to keep it active.',
                        category=NotificationCategory.ALERTS,
                        priority=NotificationPriority.HIGH,
                        content_object=instance,
                        action_url=instance.get_absolute_url(),
                        action_text="Renew Service"
                    )
                    instance.deletion_warning_sent = True
                    
                    # Send email warning
                    from .tasks import send_service_expiry_warning_email
                    send_service_expiry_warning_email(instance.id, days_left)
                    
                except ImportError:
                    logger.warning("Notifications app not available")
                except Exception as e:
                    logger.error(f"Error creating expiration warning: {str(e)}")
                    
    except Exception as e:
        logger.error(f"Error checking service expiration: {str(e)}")



@receiver(pre_delete, sender=ServiceListing)
def cleanup_service_files(sender, instance, **kwargs):
    """Clean up files when service is deleted - IMPROVED"""
    try:
        # Delete all associated images
        for image in instance.images.all():
            try:
                if image.image:
                    image.image.delete(save=False)
            except Exception as e:
                logger.warning(f"Error deleting service image: {str(e)}")
        
        # Delete all associated documents
        for document in instance.documents.all():
            try:
                if document.document:
                    document.document.delete(save=False)
            except Exception as e:
                logger.warning(f"Error deleting service document: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error cleaning up service files: {str(e)}")



@receiver(post_delete, sender=ServiceImage)
def cleanup_service_image_file(sender, instance, **kwargs):
    """Clean up image file when ServiceImage is deleted"""
    try:
        if instance.image:
            instance.image.delete(save=False)
    except Exception as e:
        logger.warning(f"Error cleaning up service image file: {str(e)}")



@receiver(post_delete, sender=ServiceDocument)
def cleanup_service_document_file(sender, instance, **kwargs):
    """Clean up document file when ServiceDocument is deleted"""
    try:
        if instance.document:
            instance.document.delete(save=False)
    except Exception as e:
        logger.warning(f"Error cleaning up service document file: {str(e)}")


@receiver(post_save, sender=ServiceInquiry)
def update_service_inquiry_stats(sender, instance, created, **kwargs):
    """Update service inquiry statistics"""
    if created:
        try:
            # Update provider's total inquiry count
            from User.models import Profile
            Profile.objects.filter(id=instance.service.provider.id).update(
                total_service_inquiries=F('total_service_inquiries') + 1
            )
        except Exception as e:
            logger.erro


@receiver(post_save, sender=ServiceInquiry)
def handle_inquiry_status_change(sender, instance, created, **kwargs):
    """Handle inquiry status changes - IMPROVED"""
    if not created and instance.status == 'responded' and instance.provider_response:
        try:
            # Notify client when provider responds
            try:
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=instance.client.user,
                    title="Service Provider Responded",
                    message=f'The provider of "{instance.service.title}" has responded to your inquiry.',
                    category=NotificationCategory.INQUIRIES,
                    priority=NotificationPriority.MEDIUM,
                    content_object=instance,
                    action_url=instance.service.get_absolute_url(),
                    action_text="View Response"
                )
                
                # Send email notification
                from .utils import send_inquiry_response_notification
                send_inquiry_response_notification(instance)
                
            except ImportError:
                logger.warning("Notifications app not available")
            except Exception as e:
                logger.error(f"Error creating inquiry response notification: {str(e)}")
                
        except Exception as e:
            logger.error(f"Error handling inquiry status change: {str(e)}")



def check_service_performance():
    """
    Function to check service performance and send notifications.
    This should be called by a scheduled task.
    """
    from django.db.models import Avg, Count
    
    # Find services with low ratings that might need attention
    low_rated_services = ServiceListing.objects.annotate(
        avg_rating=Avg('reviews__rating'),
        review_count=Count('reviews')
    ).filter(
        avg_rating__lt=3.0,
        review_count__gte=3,  # At least 3 reviews
        is_active=True,
        is_suspended=False
    )
    
    for service in low_rated_services:
        try:
            from Notifications.models import create_notification, NotificationCategory, NotificationPriority
            create_notification(
                user=service.provider.user,
                title="Service Performance Alert",
                message=f'Your service "{service.title}" has received low ratings. Consider improving based on client feedback.',
                category=NotificationCategory.ALERTS,
                priority=NotificationPriority.MEDIUM,
                content_object=service,
                action_url=service.get_absolute_url(),
                action_text="View Service"
            )
        except ImportError:
            pass


def generate_service_insights():
    """
    Function to generate service insights for providers.
    This should be called by a scheduled task for Pro users.
    """
    from django.db.models import Avg, Count, Sum
    from datetime import datetime, timedelta
    
    # Get services that haven't been updated in a while
    one_month_ago = timezone.now() - timedelta(days=30)
    stale_services = ServiceListing.objects.filter(
        updated_at__lt=one_month_ago,
        is_active=True,
        is_suspended=False
    ).select_related('provider__user')
    
    for service in stale_services:
        # Check if provider is Pro user
        try:
            if service.provider.user.account.effective_status.tier_type == 'pro':
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=service.provider.user,
                    title="Service Update Suggestion",
                    message=f'Your service "{service.title}" hasn\'t been updated in a while. Consider refreshing it to improve visibility.',
                    category=NotificationCategory.TIPS,
                    priority=NotificationPriority.LOW,
                    content_object=service,
                    action_url=f'/services/{service.id}/edit/',
                    action_text="Update Service"
                )
        except (ImportError, AttributeError):
            pass


def update_service_rankings():
    """
    Function to update service rankings based on performance.
    This should be called by a scheduled task.
    """
    from django.db.models import Avg, Count, F
    
    # Update boost scores for all services
    services = ServiceListing.objects.filter(is_active=True, is_suspended=False)
    
    for service in services:
        new_score = service.calculate_boost_score()
        if service.boost_score != new_score:
            ServiceListing.objects.filter(id=service.id).update(boost_score=new_score)


def send_inquiry_reminders():
    """
    Function to send reminders to providers about pending inquiries.
    This should be called by a scheduled task.
    """
    from datetime import timedelta
    
    # Find inquiries that are pending for more than 24 hours
    one_day_ago = timezone.now() - timedelta(days=1)
    pending_inquiries = ServiceInquiry.objects.filter(
        status='pending',
        created_at__lt=one_day_ago
    ).select_related('service__provider__user', 'client__user')
    
    for inquiry in pending_inquiries:
        try:
            from Notifications.models import create_notification, NotificationCategory, NotificationPriority
            create_notification(
                user=inquiry.service.provider.user,
                title="Pending Inquiry Reminder",
                message=f'You have a pending inquiry from {inquiry.client.user.username} for "{inquiry.service.title}". Quick responses improve your reputation.',
                category=NotificationCategory.REMINDERS,
                priority=NotificationPriority.MEDIUM,
                content_object=inquiry,
                action_url=inquiry.service.get_absolute_url(),
                action_text="Respond Now"
            )
        except ImportError:
            pass


def cleanup_old_service_data():
    """
    Function to cleanup old service data.
    This should be called by a scheduled task (weekly).
    """
    from datetime import timedelta
    
    # Archive very old inquiries (older than 1 year)
    one_year_ago = timezone.now() - timedelta(days=365)
    
    old_inquiries = ServiceInquiry.objects.filter(
        created_at__lt=one_year_ago,
        status__in=['declined', 'cancelled']
    )
    
    count = old_inquiries.count()
    old_inquiries.delete()
    
    return f"Cleaned up {count} old service inquiries"


def send_weekly_performance_summaries():
    """
    Send weekly performance summaries to Pro service providers.
    This should be called by a scheduled task (weekly).
    """
    from django.db.models import Count, Avg, Sum
    from datetime import timedelta
    
    one_week_ago = timezone.now() - timedelta(days=7)
    
    # Get Pro providers with services
    try:
        pro_providers = ServiceListing.objects.filter(
            provider__user__account__effective_status__tier_type='pro',
            is_active=True
        ).values('provider').distinct()
        
        for provider_data in pro_providers:
            provider_id = provider_data['provider']
            
            # Calculate weekly stats
            weekly_stats = {
                'new_inquiries': ServiceInquiry.objects.filter(
                    service__provider_id=provider_id,
                    created_at__gte=one_week_ago
                ).count(),
                'new_reviews': ServiceReview.objects.filter(
                    service__provider_id=provider_id,
                    created_at__gte=one_week_ago
                ).count(),
                'total_views': ServiceListing.objects.filter(
                    provider_id=provider_id
                ).aggregate(total=Sum('view_count'))['total'] or 0,
            }
            
            if weekly_stats['new_inquiries'] > 0 or weekly_stats['new_reviews'] > 0:
                from User.models import Profile
                provider = Profile.objects.get(id=provider_id)
                
                from Notifications.models import create_notification, NotificationCategory, NotificationPriority
                create_notification(
                    user=provider.user,
                    title="Weekly Performance Summary",
                    message=f'This week: {weekly_stats["new_inquiries"]} new inquiries, {weekly_stats["new_reviews"]} new reviews. Keep up the great work!',
                    category=NotificationCategory.REPORTS,
                    priority=NotificationPriority.LOW,
                    content_object=None,
                    action_url='/services/my-services/',
                    action_text="View My Services"
                )
    except (ImportError, AttributeError):
        pass

