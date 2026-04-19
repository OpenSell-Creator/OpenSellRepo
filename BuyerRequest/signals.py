from django.db.models.signals import post_save, pre_delete, post_delete, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.db.models import F
from datetime import timedelta

from .models import (
    BuyerRequest, SellerResponse, BuyerRequestImage, RequestAccess
)


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
            category=getattr(NotificationCategory, category, NotificationCategory.SYSTEM) if category else NotificationCategory.SYSTEM,
            priority=getattr(NotificationPriority, priority, NotificationPriority.NORMAL) if priority else NotificationPriority.NORMAL,
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


@receiver(post_save, sender=BuyerRequest)
def handle_request_created(sender, instance, created, **kwargs):
    """Handle actions when a new buyer request is created"""
    if created:
        # Send notification to buyer confirming request creation
        safe_create_notification(
            user=instance.buyer.user,
            title="Request Posted Successfully",
            message=f'Your request "{instance.title}" has been posted and is now visible to sellers.',
            category='SYSTEM',
            priority='LOW',
            content_object=instance,
            action_url=instance.get_absolute_url(),
            action_text="View Request"
        )
        
        # Update buyer's total requests count
        from User.models import Profile
        Profile.objects.filter(id=instance.buyer.id).update(
            total_requests_posted=F('total_requests_posted') + 1
        )


@receiver(pre_save, sender=BuyerRequest)
def check_request_expiration(sender, instance, **kwargs):
    """Check for upcoming expiration and send warnings"""
    if not hasattr(instance, '_original_deletion_warning_sent'):
        instance._original_deletion_warning_sent = instance.deletion_warning_sent

    if instance.expires_at:
        days_left = instance.days_remaining
        
        # Only send notification if:
        # 1. Days left is 1 or 3
        # 2. No warning was previously sent
        # 3. This isn't a new request (has an id)
        if (days_left in [1, 3] and 
            not instance._original_deletion_warning_sent and 
            instance.id and 
            instance.status == 'active'):
            
            safe_create_notification(
                user=instance.buyer.user,
                title=f"Request Expiring Soon!",
                message=f"Your request '{instance.title}' will expire in {days_left} days. Consider bumping it or extending the deadline.",
                category='ALERTS',
                priority='HIGH',
                content_object=instance,
                action_url=instance.get_absolute_url(),
                action_text="Bump Request"
            )
            instance.deletion_warning_sent = True


@receiver(post_save, sender=BuyerRequest)
def handle_request_status_change(sender, instance, created, **kwargs):
    """Handle buyer request status changes"""
    if not created:
        # Check if status changed to fulfilled
        if instance.status == 'fulfilled':
            # Notify all responders that request was fulfilled
            for response in instance.responses.all():
                safe_create_notification(
                    user=response.seller.user,
                    title="Request Fulfilled",
                    message=f'The request "{instance.title}" you responded to has been marked as fulfilled.',
                    category='SYSTEM',
                    priority='LOW',
                    content_object=instance,
                    action_url=instance.get_absolute_url(),
                    action_text="View Request"
                )
        
        elif instance.status == 'cancelled':
            # Notify all responders that request was cancelled
            for response in instance.responses.all():
                safe_create_notification(
                    user=response.seller.user,
                    title="Request Cancelled",
                    message=f'The request "{instance.title}" you responded to has been cancelled by the buyer.',
                    category='SYSTEM',
                    priority='LOW',
                    content_object=instance
                )


@receiver(post_save, sender=SellerResponse)
def handle_response_created(sender, instance, created, **kwargs):
    """
    Post-save signal for SellerResponse.

    response_count increment    → handled by create_response() view
    buyer notification          → handled by create_response() view (has conversation URL)
    seller stat update          → handled here, safely
    """
    if not created:
        return

    from User.models import Profile
    from django.db.models import F

    # Safely increment seller stats — individual try/except per field
    # so a missing column never crashes the response save.
    for field in ('total_responses_sent',):
        try:
            Profile.objects.filter(id=instance.seller.id).update(
                **{field: F(field) + 1}
            )
        except Exception:
            pass


@receiver(post_delete, sender=SellerResponse)
def handle_response_deleted(sender, instance, **kwargs):
    """Handle actions when a response is deleted"""
    # Decrease response count on buyer request
    BuyerRequest.objects.filter(id=instance.buyer_request.id).update(
        response_count=F('response_count') - 1
    )

"""@receiver(post_save, sender=SavedRequest)
    def handle_request_saved(sender, instance, created, **kwargs):
        if created:
            # Send notification to request owner
            safe_create_notification(
                user=instance.request.buyer.user,
                title="Request Saved",
                message=f'Someone saved your request "{instance.request.title}"',
                category='SAVES',
                priority='LOW',
                content_object=instance.request,
                action_url=instance.request.get_absolute_url(),
                action_text="View Request"
            )"""


@receiver(pre_delete, sender=BuyerRequest)
def cleanup_request_files(sender, instance, **kwargs):
    """Clean up files when request is deleted (following Product_Listing pattern)"""
    # Delete all associated images
    for image in instance.images.all():
        try:
            image.image.delete(save=False)
        except Exception:
            pass
    
    # Delete all conversations and messages
    for conversation in instance.conversations.all():
        conversation.delete()


@receiver(post_delete, sender=BuyerRequestImage)
def cleanup_image_file(sender, instance, **kwargs):
    """Clean up image file when BuyerRequestImage is deleted"""
    try:
        instance.image.delete(save=False)
    except Exception:
        pass


@receiver(post_save, sender=BuyerRequest)
def update_request_boost_score(sender, instance, created, **kwargs):
    """Update boost score when request is saved"""
    if not created:  # Only update for existing requests
        # Calculate and update boost score
        calculated_score = instance.calculate_boost_score()
        if instance.boost_score != calculated_score:
            BuyerRequest.objects.filter(pk=instance.pk).update(boost_score=calculated_score)


@receiver(post_save, sender='User.ItemReport')
def handle_buyer_request_report_created(sender, instance, created, **kwargs):
    """
    Handle actions when a buyer request is reported using unified ItemReport
    """
    if not created:
        return
    
    # Check if this report is for a BuyerRequest
    from django.contrib.contenttypes.models import ContentType
    from BuyerRequest.models import BuyerRequest
    
    request_ct = ContentType.objects.get_for_model(BuyerRequest)
    
    if instance.content_type != request_ct:
        return  # Not a buyer request report
    
    try:
        buyer_request = BuyerRequest.objects.get(id=instance.object_id)
        report_count = buyer_request.reports.count()
        
        # Auto-suspend if threshold reached (5 reports)
        if report_count >= 5 and not buyer_request.is_suspended:
            try:
                # Get a superuser for auto-suspension
                from django.contrib.auth.models import User
                superuser = User.objects.filter(is_superuser=True).first()
                
                if superuser:
                    buyer_request.suspend(
                        superuser, 
                        f"Auto-suspended after receiving {report_count} reports."
                    )
                    
                    # Notify the buyer about suspension
                    safe_create_notification(
                        user=buyer_request.buyer.user,
                        title="Request Suspended",
                        message=f'Your request "{buyer_request.title}" has been suspended due to multiple reports.',
                        category='ALERTS',
                        priority='URGENT',
                        content_object=buyer_request,
                        action_text="Contact Support"
                    )
            except Exception as e:
                print(f"Error auto-suspending request: {e}")
    
    except BuyerRequest.DoesNotExist:
        pass

# Utility functions for scheduled tasks
def check_expiring_requests():
    """
    Function to check for expiring requests and send notifications.
    This should be called by a scheduled task (following existing task pattern).
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Find requests expiring in 3 days or 1 day
    three_days_from_now = timezone.now() + timedelta(days=3)
    one_day_from_now = timezone.now() + timedelta(days=1)
    
    expiring_requests = BuyerRequest.objects.filter(
        status='active',
        is_suspended=False,
        expires_at__lte=three_days_from_now,
        expires_at__gt=timezone.now(),
        deletion_warning_sent=False
    ).select_related('buyer__user')
    
    for request in expiring_requests:
        days_remaining = (request.expires_at - timezone.now()).days
        
        if days_remaining in [1, 3]:
            safe_create_notification(
                user=request.buyer.user,
                title=f"Request Expiring in {days_remaining} Days",
                message=f'Your request "{request.title}" will expire soon. Consider bumping it or extending the deadline.',
                category='ALERTS',
                priority='HIGH',
                content_object=request,
                action_url=request.get_absolute_url(),
                action_text="Bump Request"
            )
            
            # Mark warning as sent
            BuyerRequest.objects.filter(id=request.id).update(deletion_warning_sent=True)


def mark_expired_requests():
    """
    Function to mark expired requests as expired.
    This should be called by a scheduled task (following existing pattern).
    """
    from django.utils import timezone
    
    expired_requests = BuyerRequest.objects.filter(
        status='active',
        expires_at__lte=timezone.now()
    )
    
    count = 0
    for request in expired_requests:
        request.status = 'expired'
        request.save(update_fields=['status'])
        
        # Notify buyer about expiration
        safe_create_notification(
            user=request.buyer.user,
            title="Request Expired",
            message=f'Your request "{request.title}" has expired. You can repost it or create a new one.',
            category='ALERTS',
            priority='MEDIUM',
            content_object=request,
            action_text="Create New Request"
        )
        count += 1
    
    return count


def notify_interested_sellers():
    """
    Function to notify sellers about new requests in their categories.
    This should be called by a scheduled task.
    """
    from django.utils import timezone
    from datetime import timedelta
    
    # Find requests created in the last hour
    one_hour_ago = timezone.now() - timedelta(hours=1)
    new_requests = BuyerRequest.objects.filter(
        created_at__gte=one_hour_ago,
        status='active',
        is_suspended=False
    ).select_related('buyer__user', 'category')
    
    notification_count = 0
    for request in new_requests:
        try:
            # Find sellers who might be interested
            # This could be enhanced with more sophisticated matching
            from User.models import Profile
            
            # Get sellers in the same category (for product requests)
            if request.category:
                interested_sellers = Profile.objects.filter(
                    seller_listings__category=request.category,
                    user__account__effective_status__tier_type='pro'  # Only notify Pro users
                ).distinct()
                
                for seller in interested_sellers[:10]:  # Limit to 10 notifications
                    safe_create_notification(
                        user=seller.user,
                        title="New Request in Your Category",
                        message=f'New request posted: "{request.title}" in {request.category.name}',
                        category='SYSTEM',
                        priority='LOW',
                        content_object=request,
                        action_url=request.get_absolute_url(),
                        action_text="View Request"
                    )
                    notification_count += 1
                    
        except Exception as e:
            print(f"Error notifying sellers about request {request.id}: {e}")
    
    return notification_count