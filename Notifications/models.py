from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from datetime import timedelta

class NotificationCategory(models.TextChoices):
    ANNOUNCEMENT = 'announcement', '📢 Announcements'
    SYSTEM = 'system', '⚙️ System'
    NEWS = 'news', '📰 News & Updates'
    REVIEW = 'review', '⭐ Reviews'
    SAVES = 'saves', '❤️ Saves & Favorites'
    MILESTONES = 'milestones', '🎯 Milestones'
    ALERTS = 'alerts', '🚨 Alerts'

class NotificationPriority(models.TextChoices):
    LOW = 'low', 'Low'
    NORMAL = 'normal', 'Normal'
    HIGH = 'high', 'High'
    URGENT = 'urgent', 'Urgent'

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.ANNOUNCEMENT
    )
    priority = models.CharField(
        max_length=10,
        choices=NotificationPriority.choices,
        default=NotificationPriority.NORMAL
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=36, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Action URL for quick actions
    action_url = models.URLField(null=True, blank=True)
    action_text = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['category']),
            models.Index(fields=['is_read']),
            models.Index(fields=['priority']),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def get_content_type_name(self):
        """Get the model name of the content object"""
        if self.content_object:
            return self.content_type.model
        return ''
    
    def get_icon(self):
        """Get icon based on category"""
        icons = {
            'announcement': '📢',
            'system': '⚙️',
            'news': '📰',
            'review': '⭐',
            'saves': '❤️',
            'milestones': '🎯',
            'alerts': '🚨',
        }
        return icons.get(self.category, '📢')
    
    def get_priority_class(self):
        """Get CSS class for priority styling"""
        return {
            'low': 'priority-low',
            'normal': 'priority-normal',
            'high': 'priority-high',
            'urgent': 'priority-urgent'
        }.get(self.priority, 'priority-normal')
    
    @classmethod
    def delete_old_notifications(cls, days=30):
        """Delete notifications older than specified days"""
        cutoff = timezone.now() - timedelta(days=days)
        return cls.objects.filter(created_at__lte=cutoff).delete()

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Existing preferences
    review_notifications = models.BooleanField(default=True, help_text="Get notified about new reviews")
    save_notifications = models.BooleanField(default=True, help_text="Get notified when someone saves your listings")
    view_milestone_notifications = models.BooleanField(default=True, help_text="Get notified about view milestones")
    system_notifications = models.BooleanField(default=True, help_text="Get notified about system updates")
    deletion_warnings = models.BooleanField(default=True, help_text="Get notified when listings are about to expire")
    stock_alerts = models.BooleanField(default=True, help_text="Get notified about low stock")
    
    # New preferences
    price_drop_alerts = models.BooleanField(default=True, help_text="Get notified about price drops on saved items")
    reply_notifications = models.BooleanField(default=True, help_text="Get notified about replies to your reviews")
    report_notifications = models.BooleanField(default=True, help_text="Get notified if your listings are reported")
    milestone_achievements = models.BooleanField(default=True, help_text="Get notified about milestones and achievements")
    
    # Email preferences
    email_notifications = models.BooleanField(default=False, help_text="Receive notifications via email")
    email_digest = models.BooleanField(default=False, help_text="Receive weekly email digest")
    
    # Push notification preferences (for future PWA implementation)
    push_notifications = models.BooleanField(default=True, help_text="Receive browser push notifications")
    
    # Notification frequency
    FREQUENCY_CHOICES = [
        ('instant', 'Instant'),
        ('hourly', 'Hourly digest'),
        ('daily', 'Daily digest'),
    ]
    frequency = models.CharField(max_length=10, choices=FREQUENCY_CHOICES, default='instant')

    def __str__(self):
        return f"Preferences for {self.user.username}"

    @classmethod
    def get_or_create_preferences(cls, user):
        """Get or create notification preferences for user"""
        preferences, created = cls.objects.get_or_create(
            user=user,
            defaults={
                'review_notifications': True,
                'save_notifications': True,
                'view_milestone_notifications': True,
                'system_notifications': True,
                'deletion_warnings': True,
                'stock_alerts': True,
                'price_drop_alerts': True,
                'reply_notifications': True,
                'report_notifications': True,
                'milestone_achievements': True,
            }
        )
        return preferences

def create_notification(user, title, message, category=NotificationCategory.ANNOUNCEMENT, 
                        content_object=None, priority=NotificationPriority.NORMAL, 
                        action_url=None, action_text=None):
    """
    Utility function to create notifications
    
    Args:
        user: User to send notification to
        title: Notification title
        message: Notification message
        category: NotificationCategory choice
        content_object: Related model instance (optional)
        priority: NotificationPriority choice
        action_url: URL for quick action (optional)
        action_text: Text for action button (optional)
    """
    # Check if user has preferences for this type of notification
    preferences = NotificationPreference.get_or_create_preferences(user)
    
    # Map categories to preference fields
    category_prefs = {
        NotificationCategory.REVIEW: preferences.review_notifications,
        NotificationCategory.SAVES: preferences.save_notifications,
        NotificationCategory.MILESTONES: preferences.milestone_achievements,
        NotificationCategory.SYSTEM: preferences.system_notifications,
        NotificationCategory.ALERTS: preferences.deletion_warnings or preferences.stock_alerts,
        NotificationCategory.NEWS: preferences.price_drop_alerts,
        NotificationCategory.ANNOUNCEMENT: True,  # Always send announcements
    }
    
    # Check if user wants this type of notification
    if not category_prefs.get(category, True):
        return None
    
    return Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        category=category,
        priority=priority,
        content_object=content_object,
        action_url=action_url,
        action_text=action_text
    )

# Bulk notification utilities
def create_bulk_notification(users, title, message, category=NotificationCategory.ANNOUNCEMENT):
    """Create notification for multiple users"""
    notifications = []
    for user in users:
        notifications.append(
            Notification(
                recipient=user,
                title=title,
                message=message,
                category=category
            )
        )
    return Notification.objects.bulk_create(notifications)

def mark_all_read(user):
    """Mark all notifications as read for a user"""
    return Notification.objects.filter(
        recipient=user, 
        is_read=False
    ).update(
        is_read=True, 
        read_at=timezone.now()
    )