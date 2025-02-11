from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist

from Home.models import Product_Listing, Review, SavedProduct, ReviewReply
from .models import (
    Notification,
    NotificationPreference,
    NotificationCategory,
    create_notification
)

# User Preference Signal
@receiver(post_save, sender=User)
def create_user_notification_preferences(sender, instance, created, **kwargs):
    """Create notification preferences when a new user is created"""
    if created:
        NotificationPreference.objects.get_or_create(user=instance)

# Product Listing Signals
@receiver(pre_save, sender=Product_Listing)
def handle_listing_notifications(sender, instance, **kwargs):
    """Handle all product listing related notifications"""
    if not instance.id:  # Skip if new instance
        return
    
    try:
        # Get the original instance if it exists
        original = Product_Listing.objects.get(id=instance.id)
    except Product_Listing.DoesNotExist:
        return

    # Handle expiration warnings
    if instance.expiration_date != original.expiration_date:
        instance.deletion_warning_sent = False
        days_left = instance.days_until_deletion
        if days_left in [1, 3] and not original.deletion_warning_sent:
            prefs = NotificationPreference.objects.filter(
                user=instance.seller.user,
                system_notifications=True
            ).exists()
            
            if prefs:
                create_notification(
                    user=instance.seller.user,
                    title="Listing Expiring Soon!",
                    message=f"Your listing '{instance.title}' will expire in {days_left} days",
                    category=NotificationCategory.SYSTEM,
                    content_object=instance
                )
                instance.deletion_warning_sent = True

    # Handle low stock warnings
    if instance.quantity <= 5 and instance.quantity < original.quantity:
        prefs = NotificationPreference.objects.filter(
            user=instance.seller.user,
            system_notifications=True
        ).exists()
        
        if prefs:
            create_notification(
                user=instance.seller.user,
                title="Low Stock Alert",
                message=f"Your listing '{instance.title}' is running low on stock (Quantity: {instance.quantity})",
                category=NotificationCategory.SYSTEM,
                content_object=instance
            )

# SavedProduct Signal
@receiver(post_save, sender=SavedProduct)
def notify_on_save(sender, instance, created, **kwargs):
    """Notify seller when their product is saved by a user"""
    if created:  # Only notify on new saves
        prefs = NotificationPreference.objects.filter(
            user=instance.product.seller.user,
            save_notifications=True
        ).exists()
        
        if prefs:
            create_notification(
                user=instance.product.seller.user,
                title="Product Saved!",
                message=f"{instance.user.username} saved your listing '{instance.product.title}'",
                category=NotificationCategory.NEWS,
                content_object=instance.product
            )

# Review Signal
@receiver(post_save, sender=Review)
def notify_on_review(sender, instance, created, **kwargs):
    """Notify seller when their product receives a review"""
    if created and instance.review_type == 'product':  # Only notify for product reviews
        try:
            prefs = NotificationPreference.objects.filter(
                user=instance.product.seller.user,
                review_notifications=True
            ).exists()
            
            if prefs:
                create_notification(
                    user=instance.product.seller.user,
                    title="New Review Received",
                    message=f"{instance.reviewer.username} left a {instance.rating}-star review on '{instance.product.title}'",
                    category=NotificationCategory.NEWS,
                    content_object=instance
                )
        except ObjectDoesNotExist:
            # Handle case where product or seller might not exist
            pass
        
        
# Review Reply Signal
@receiver(post_save, sender=ReviewReply)
def notify_on_review_reply(sender, instance, created, **kwargs):
    if created:
        review = instance.review
        replier = instance.reviewer
        recipient = None

        # Determine notification recipient
        if review.review_type == 'product':
            seller_user = review.product.seller.user
            if replier == seller_user:
                recipient = review.reviewer  # Notify buyer
        else:  # Seller review
            seller_user = review.seller.user
            if replier == seller_user:
                recipient = review.reviewer  # Notify reviewer

        # Send notification if valid recipient exists
        if recipient and recipient != replier:
            prefs = NotificationPreference.objects.filter(
                user=recipient,
                review_notifications=True
            ).exists()
            
            if prefs:
                create_notification(
                    user=recipient,
                    title="New Reply to Your Review",
                    message=f"{replier.username} replied to your {review.get_review_type_display()}",
                    category=NotificationCategory.NEWS,
                    content_object=instance
                )
# View Milestone Signal
@receiver(pre_save, sender=Product_Listing)
def notify_on_view_milestone(sender, instance, **kwargs):
    """Notify seller when their product reaches view milestones"""
    if not instance.id:  # Skip if new instance
        return
        
    try:
        original = Product_Listing.objects.get(id=instance.id)
    except Product_Listing.DoesNotExist:
        return

    milestones = [2, 100, 500, 1000, 5000, 10000]
    
    # Get the last milestone that was crossed
    last_milestone = max((m for m in milestones if original.view_count >= m), default=0)
    # Get the new milestone that's been reached
    new_milestone = next((m for m in milestones if instance.view_count >= m > last_milestone), None)
    
    if new_milestone:
        prefs = NotificationPreference.objects.filter(
            user=instance.seller.user,
            view_milestone_notifications=True
        ).exists()
        
        if prefs:
            create_notification(
                user=instance.seller.user,
                title="View Milestone Reached!",
                message=f"Congratulations! Your listing '{instance.title}' has reached {new_milestone} views!",
                category=NotificationCategory.NEWS,
                content_object=instance
            )