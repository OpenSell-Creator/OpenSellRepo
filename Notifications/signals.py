# notifications/signals.py
from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count
from datetime import timedelta, date

from Home.models import Product_Listing, Review, ReviewReply
from User.models import ItemReport, SavedItem
from .models import Notification, NotificationPreference, NotificationCategory, NotificationPriority, create_notification

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
# REPLACE the handle_product_save_notifications function in Notifications/signals.py

@receiver(post_save, sender=SavedItem)
def handle_product_save_notifications(sender, instance, created, **kwargs):
    """
    UNIFIED: Handle notifications when someone saves a product, service, or request
    """
    if not created:
        return
    
    # Get the actual item using content_object (generic foreign key)
    item = instance.content_object
    
    if not item:
        return  # Item was deleted
    
    # Determine owner and item type based on what was saved
    owner = None
    item_type = None
    item_title = None
    
    # Check if it's a Product
    if hasattr(item, 'seller') and hasattr(item.seller, 'user'):
        owner = item.seller.user
        item_type = 'product'
        item_title = getattr(item, 'title', str(item))
    
    # Check if it's a Service
    elif hasattr(item, 'provider') and hasattr(item.provider, 'user'):
        owner = item.provider.user
        item_type = 'service'
        item_title = getattr(item, 'title', str(item))
    
    # Check if it's a Buyer Request
    elif hasattr(item, 'buyer') and hasattr(item.buyer, 'user'):
        owner = item.buyer.user
        item_type = 'request'
        item_title = getattr(item, 'title', str(item))
    
    # If we couldn't determine the owner, skip notification
    if not owner or owner == instance.user:
        return  # Don't notify if owner saved their own item
    
    # Check if owner wants save notifications
    prefs = NotificationPreference.objects.filter(
        user=owner,
        save_notifications=True
    ).first()
    
    if not prefs:
        return
    
    # Get total saves count for this item
    from django.contrib.contenttypes.models import ContentType
    content_type = ContentType.objects.get_for_model(item)
    total_saves = SavedItem.objects.filter(
        content_type=content_type,
        object_id=str(item.id)
    ).count()
    
    # Create notification based on item type
    notification_messages = {
        'product': f"Someone saved your product '{item_title}' ({total_saves} total saves)",
        'service': f"Someone saved your service '{item_title}' ({total_saves} total saves)",
        'request': f"A seller saved your request '{item_title}' ({total_saves} total saves)"
    }
    
    notification_titles = {
        'product': "❤️ Product Saved",
        'service': "🔖 Service Saved",
        'request': "🔍 Request Saved"
    }
    
    create_notification(
        user=owner,
        title=notification_titles.get(item_type, "📌 Item Saved"),
        message=notification_messages.get(item_type, f"Someone saved your {item_type}"),
        category=NotificationCategory.SAVES,
        priority=NotificationPriority.LOW,
        content_object=item
    )
    
    # Milestone notifications for saves (5, 10, 25, 50, 100)
    if total_saves in [5, 10, 25, 50, 100]:
        milestone_messages = {
            'product': f"Your product '{item_title}' has reached {total_saves} saves! It's really popular.",
            'service': f"Your service '{item_title}' has reached {total_saves} saves! Great interest!",
            'request': f"Your request '{item_title}' has reached {total_saves} saves from sellers!"
        }
        
        create_notification(
            user=owner,
            title=f"🔥 {total_saves} Saves Milestone!",
            message=milestone_messages.get(item_type, f"Your {item_type} reached {total_saves} saves!"),
            category=NotificationCategory.MILESTONES,
            priority=NotificationPriority.NORMAL,
            content_object=item
        )
# Item Report Signals
@receiver(post_save, sender=ItemReport)
def handle_item_report_notifications(sender, instance, created, **kwargs):
    """
    UNIFIED: Handle notifications for product, service, and request reports
    """
    if not created:
        return
    
    # Get the item owner
    item = instance.content_object
    if not item:
        return  # Item was deleted
    
    # Determine owner based on item type
    owner = None
    if hasattr(item, 'seller'):  # Product
        owner = item.seller.user
    elif hasattr(item, 'provider'):  # Service
        owner = item.provider.user
    elif hasattr(item, 'buyer'):  # Buyer Request
        owner = item.buyer.user
    
    if owner:
        # Notify owner about report
        create_notification(
            user=owner,
            title=f"⚠️ {instance.item_type_display} Reported",
            message=f'Your {instance.item_type} "{instance.item_title}" was reported for: {instance.get_reason_display()}. Our team will review it.',
            category=NotificationCategory.ALERTS,
            priority=NotificationPriority.HIGH,
            content_object=item
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
            # FIXED: Use content_type and object_id instead of product field
            from django.contrib.contenttypes.models import ContentType
            
            product_ct = ContentType.objects.get_for_model(Product_Listing)
            saved_items = SavedItem.objects.filter(
                content_type=product_ct,
                object_id=str(instance.id)
            ).select_related('user')
            
            for saved_item in saved_items:
                # Check if user wants price drop alerts
                prefs = NotificationPreference.objects.filter(
                    user=saved_item.user,
                    price_drop_alerts=True
                ).first()
                
                if prefs:
                    price_diff = original.price - instance.price
                    discount_percent = (price_diff / original.price) * 100
                    
                    create_notification(
                        user=saved_item.user,
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