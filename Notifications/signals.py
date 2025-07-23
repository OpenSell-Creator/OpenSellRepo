# notifications/signals.py
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from datetime import timedelta, date

from Home.models import Product_Listing, Review, SavedProduct, ReviewReply, ProductReport
from .models import (
    Notification,
    NotificationPreference,
    NotificationCategory,
    NotificationPriority,
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
        original = Product_Listing.objects.get(id=instance.id)
    except Product_Listing.DoesNotExist:
        return

    # Handle expiration warnings - FIXED datetime issue
    if hasattr(instance, 'expiration_date') and instance.expiration_date:
        # Convert both to date objects for comparison
        if hasattr(instance.expiration_date, 'date'):
            # expiration_date is a datetime object
            expiration_date = instance.expiration_date.date()
        else:
            # expiration_date is already a date object
            expiration_date = instance.expiration_date
        
        today = timezone.now().date()
        days_left = (expiration_date - today).days
        
        if days_left in [1, 3, 7] and not getattr(instance, 'deletion_warning_sent', False):
            prefs = NotificationPreference.objects.filter(
                user=instance.seller.user,
                deletion_warnings=True
            ).first()
            
            if prefs:
                if days_left == 1:
                    urgency = "expires today!"
                    priority = NotificationPriority.URGENT
                elif days_left == 3:
                    urgency = f"expires in {days_left} days"
                    priority = NotificationPriority.HIGH
                else:
                    urgency = f"expires in {days_left} days"
                    priority = NotificationPriority.NORMAL
                
                create_notification(
                    user=instance.seller.user,
                    title=f"⚠️ Listing {urgency}",
                    message=f"Your listing '{instance.title}' will expire in {days_left} day{'s' if days_left > 1 else ''}. Renew it to keep it active.",
                    category=NotificationCategory.ALERTS,
                    priority=priority,
                    content_object=instance
                )
                instance.deletion_warning_sent = True

    # Handle stock alerts (if you have stock field)
    if hasattr(instance, 'stock') and hasattr(original, 'stock'):
        if instance.stock <= 5 and original.stock > 5:
            prefs = NotificationPreference.objects.filter(
                user=instance.seller.user,
                stock_alerts=True
            ).first()
            
            if prefs:
                create_notification(
                    user=instance.seller.user,
                    title="📦 Low Stock Alert",
                    message=f"Your listing '{instance.title}' is running low on stock ({instance.stock} remaining).",
                    category=NotificationCategory.ALERTS,
                    priority=NotificationPriority.HIGH,
                    content_object=instance
                )

@receiver(post_save, sender=Product_Listing)
def handle_new_listing_notifications(sender, instance, created, **kwargs):
    """Handle notifications for new listings"""
    if created:
        # Welcome notification for first listing
        seller_listings_count = Product_Listing.objects.filter(seller=instance.seller).count()
        
        if seller_listings_count == 1:
            create_notification(
                user=instance.seller.user,
                title="🎉 Welcome to selling!",
                message=f"Your first listing '{instance.title}' is now live! Good luck with your sale.",
                category=NotificationCategory.ANNOUNCEMENT,
                priority=NotificationPriority.NORMAL,
                content_object=instance
            )
        
        # Milestone notifications for listing count
        elif seller_listings_count in [5, 10, 25, 50, 100]:
            create_notification(
                user=instance.seller.user,
                title=f"🌟 {seller_listings_count} Listings Milestone!",
                message=f"Congratulations! You've now created {seller_listings_count} listings. Keep up the great work!",
                category=NotificationCategory.MILESTONES,
                priority=NotificationPriority.NORMAL,
                content_object=instance
            )

# Review Signals
@receiver(post_save, sender=Review)
def handle_review_notifications(sender, instance, created, **kwargs):
    """Handle notifications for new reviews"""
    if created:
        if instance.product:
            # Notify seller about product review
            prefs = NotificationPreference.objects.filter(
                user=instance.product.seller.user,
                review_notifications=True
            ).first()
            
            if prefs:
                stars = "⭐" * instance.rating
                create_notification(
                    user=instance.product.seller.user,
                    title=f"📝 New Review Received",
                    message=f"{instance.reviewer.username} left a {instance.rating}-star review on '{instance.product.title}': {stars}",
                    category=NotificationCategory.REVIEW,
                    priority=NotificationPriority.NORMAL,
                    content_object=instance
                )
        
        elif hasattr(instance, 'seller') and instance.seller:
            # Notify seller about seller review
            prefs = NotificationPreference.objects.filter(
                user=instance.seller.user,
                review_notifications=True
            ).first()
            
            if prefs:
                stars = "⭐" * instance.rating
                create_notification(
                    user=instance.seller.user,
                    title=f"📝 New Seller Review",
                    message=f"{instance.reviewer.username} left you a {instance.rating}-star review: {stars}",
                    category=NotificationCategory.REVIEW,
                    priority=NotificationPriority.NORMAL,
                    content_object=instance
                )

@receiver(post_save, sender=ReviewReply)
def handle_review_reply_notifications(sender, instance, created, **kwargs):
    """Handle notifications for review replies"""
    if created:
        # Notify original reviewer about seller's reply
        create_notification(
            user=instance.review.reviewer,
            title="💬 Seller replied to your review",
            message=f"{instance.reviewer.username} replied to your review on '{instance.review.product.title if instance.review.product else 'their profile'}'",
            category=NotificationCategory.REVIEW,
            priority=NotificationPriority.NORMAL,
            content_object=instance
        )

# Saved Product Signals
@receiver(post_save, sender=SavedProduct)
def handle_product_save_notifications(sender, instance, created, **kwargs):
    """Handle notifications when someone saves a product"""
    if created:
        prefs = NotificationPreference.objects.filter(
            user=instance.product.seller.user,
            save_notifications=True
        ).first()
        
        if prefs:
            # Get total saves count
            total_saves = SavedProduct.objects.filter(product=instance.product).count()
            
            create_notification(
                user=instance.product.seller.user,
                title="❤️ Product Saved",
                message=f"Someone saved your listing '{instance.product.title}' ({total_saves} total saves)",
                category=NotificationCategory.SAVES,
                priority=NotificationPriority.LOW,
                content_object=instance.product
            )
            
            # Milestone notifications for saves
            if total_saves in [5, 10, 25, 50, 100]:
                create_notification(
                    user=instance.product.seller.user,
                    title=f"🔥 {total_saves} Saves Milestone!",
                    message=f"Your listing '{instance.product.title}' has reached {total_saves} saves! It's really popular.",
                    category=NotificationCategory.MILESTONES,
                    priority=NotificationPriority.NORMAL,
                    content_object=instance.product
                )

# Product Report Signals
@receiver(post_save, sender=ProductReport)
def handle_product_report_notifications(sender, instance, created, **kwargs):
    """Handle notifications for product reports"""
    if created:
        # Notify seller about report (they should know their product was reported)
        create_notification(
            user=instance.product.seller.user,
            title="⚠️ Product Reported",
            message=f"Your listing '{instance.product.title}' was reported for: {instance.get_reason_display()}. Our team will review it.",
            category=NotificationCategory.ALERTS,
            priority=NotificationPriority.HIGH,
            content_object=instance.product
        )

# View Milestone Notifications (call this from your product detail view)
def check_view_milestones(product, current_views):
    """Call this function when a product view count is updated"""
    milestones = [100, 500, 1000, 5000, 10000]
    
    for milestone in milestones:
        if current_views >= milestone:
            # Check if we haven't sent this milestone notification yet
            existing = Notification.objects.filter(
                recipient=product.seller.user,
                title__contains=f"{milestone} Views",
                content_type__model='product_listing',
                object_id=str(product.id)
            ).exists()
            
            if not existing:
                prefs = NotificationPreference.objects.filter(
                    user=product.seller.user,
                    view_milestone_notifications=True
                ).first()
                
                if prefs:
                    create_notification(
                        user=product.seller.user,
                        title=f"👀 {milestone} Views Milestone!",
                        message=f"Your listing '{product.title}' has reached {milestone:,} views! Great visibility.",
                        category=NotificationCategory.MILESTONES,
                        priority=NotificationPriority.NORMAL,
                        content_object=product
                    )

# Price Drop Notifications (call this when price is updated)
@receiver(pre_save, sender=Product_Listing)
def handle_price_change_notifications(sender, instance, **kwargs):
    """Handle notifications for price changes to saved products"""
    if not instance.id:
        return
    
    try:
        original = Product_Listing.objects.get(id=instance.id)
    except Product_Listing.DoesNotExist:
        return
    
    if hasattr(instance, 'price') and hasattr(original, 'price'):
        if instance.price < original.price:
            # Price dropped - notify users who saved this product
            saved_users = SavedProduct.objects.filter(product=instance).select_related('user')
            
            for saved_product in saved_users:
                # Check if user wants price drop alerts
                prefs = NotificationPreference.objects.filter(
                    user=saved_product.user,
                    price_drop_alerts=True
                ).first()
                
                if prefs:
                    price_diff = original.price - instance.price
                    discount_percent = (price_diff / original.price) * 100
                    
                    create_notification(
                        user=saved_product.user,
                        title="💰 Price Drop Alert!",
                        message=f"'{instance.title}' price dropped by {discount_percent:.0f}%! Now: ₦{instance.price:,.0f} (was ₦{original.price:,.0f})",
                        category=NotificationCategory.NEWS,
                        priority=NotificationPriority.HIGH,
                        content_object=instance
                    )

# Cleanup old notifications (run this periodically)
def cleanup_old_notifications():
    """Clean up notifications older than 30 days"""
    cutoff_date = timezone.now() - timedelta(days=30)
    old_notifications = Notification.objects.filter(created_at__lt=cutoff_date)
    count = old_notifications.count()
    old_notifications.delete()
    return count