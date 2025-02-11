from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Product_Listing
from Notifications.models import create_notification, NotificationPreference, Notification


@receiver(pre_save, sender=Product_Listing)
def check_listing_expiration(sender, instance, **kwargs):
    if not hasattr(instance, '_original_deletion_warning_sent'):
        instance._original_deletion_warning_sent = instance.deletion_warning_sent

    if instance.expiration_date:
        days_left = instance.days_until_deletion
        
        # Only send notification if:
        # 1. Days left is 1 or 3
        # 2. No warning was previously sent
        # 3. This isn't a new listing (has an id)
        if (days_left in [1, 3] and 
            not instance._original_deletion_warning_sent and 
            instance.id):
            
            prefs = NotificationPreference.objects.get_or_create(
                user=instance.seller.user
            )[0]
            
            if prefs.system_notifications:  # Assuming you have this field
                create_notification(
                    user=instance.seller.user,
                    title=f"Listing Expiring Soon!",
                    message=f"Your listing '{instance.title}' will expire in {days_left} days",
                    category="SYSTEM",  # Make sure this matches your NotificationCategory choices
                    content_object=instance
                )
                instance.deletion_warning_sent = True

@receiver(pre_save, sender=Product_Listing)
def check_expiration_warning(sender, instance, **kwargs):
    if instance.expiration_date:
        days_left = instance.days_until_deletion
        if days_left in [1, 3] and not instance.deletion_warning_sent:
            create_notification(
                user=instance.seller.user,
                title=f"Listing Expiring Soon!",
                message=f"Your listing '{instance.title}' will expire in {days_left} days",
                category="system",
                content_object=instance
            )
            instance.deletion_warning_sent = True