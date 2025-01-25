from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class NotificationCategory(models.TextChoices):
    ANNOUNCEMENT = 'announcement', 'Announcement'
    SYSTEM = 'system', 'System Settings'
    NEWS = 'news', 'News'

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)
    title = models.CharField(max_length=255, default=False)
    message = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.ANNOUNCEMENT
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # For linking to specific objects (listings, reviews, etc.)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.CharField(max_length=36, null=True)  # Using CharField for UUID compatibility
    content_object = GenericForeignKey('content_type', 'object_id')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    pass

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    review_notifications = models.BooleanField(default=True)
    save_notifications = models.BooleanField(default=True)
    view_milestone_notifications = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)

    def __str__(self):
        return f"Notification preferences for {self.user.username}"
    pass

    @classmethod
    def get_or_create_preferences(cls, user):
        """Utility method to get or create preferences for a user"""
        preferences, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'review_notifications': True,
                'save_notifications': True,
                'view_milestone_notifications': True,
                'system_notifications': True
            }
        )
        return preferences

def create_notification(user, title, message, category, content_object=None):
    """Utility function to create notifications"""
    return Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        category=category,
        content_object=content_object
    )

# Signal to create notification preferences when a new user is created
@receiver(post_save, sender=User)
def create_user_notification_preferences(sender, instance, created, **kwargs):
    if created:
        NotificationPreference.get_or_create_preferences(instance)

# Signal for saved products
@receiver(post_save, sender='Home.SavedProduct')
def notify_on_save(sender, instance, created, **kwargs):
    if created:
        preferences = NotificationPreference.objects.filter(
            user=instance.product.seller.user,
            save_notifications=True
        ).exists()
        
        if preferences:
            create_notification(
                user=instance.product.seller.user,
                title="Listing Saved",
                message=f"{instance.user.username} saved your listing '{instance.product.title}'",
                category=NotificationCategory.NEWS,
                content_object=instance.product
            )

# Signal for view milestones
@receiver(post_save, sender='Home.Product_Listing')
def notify_on_view_milestone(sender, instance, **kwargs):
    milestones = [100, 500, 1000, 5000, 10000]
    
    # Get the last notified milestone from instance
    last_milestone = getattr(instance, '_last_milestone', 0)
    
    # Find the next milestone that has been reached
    reached_milestone = next(
        (m for m in milestones if instance.view_count >= m > last_milestone),
        None
    )
    
    if reached_milestone:
        preferences = NotificationPreference.objects.filter(
            user=instance.seller.user,
            view_milestone_notifications=True
        ).exists()
        
        if preferences:
            create_notification(
                user=instance.seller.user,
                title=f"View Milestone Reached!",
                message=f"Your listing '{instance.title}' has reached {reached_milestone} views!",
                category=NotificationCategory.NEWS,
                content_object=instance
            )
            
            # Update the last milestone
            instance._last_milestone = reached_milestone

# Optional: Signal for reviews
@receiver(post_save, sender='Home.Review')
def notify_on_review(sender, instance, created, **kwargs):
    if created:
        preferences = NotificationPreference.objects.filter(
            user=instance.product.seller.user,
            review_notifications=True
        ).exists()
        
        if preferences:
            create_notification(
                user=instance.product.seller.user,
                title="New Review",
                message=f"{instance.user.username} left a review on '{instance.product.title}'",
                category=NotificationCategory.NEWS,
                content_object=instance
            )

