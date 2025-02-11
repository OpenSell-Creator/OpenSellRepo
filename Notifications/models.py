from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

class NotificationCategory(models.TextChoices):
    ANNOUNCEMENT = 'announcement', 'Announcement'
    SYSTEM = 'system', 'System Settings'
    NEWS = 'news', 'News'

class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255, default='')
    message = models.TextField()
    category = models.CharField(
        max_length=20,
        choices=NotificationCategory.choices,
        default=NotificationCategory.ANNOUNCEMENT
    )
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.CharField(max_length=36, null=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
    def get_content_type_name(self):
        """Get the model name of the content object"""
        if self.content_object:
            return self.content_type.model
        return ''
    
    @classmethod
    def delete_old_notifications(cls, days=30):
        cutoff = timezone.now() - timezone.timedelta(days=days)
        cls.objects.filter(created_at__lte=cutoff).delete()

class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    review_notifications = models.BooleanField(default=True)
    save_notifications = models.BooleanField(default=True)
    view_milestone_notifications = models.BooleanField(default=True)
    system_notifications = models.BooleanField(default=True)
    deletion_warnings = models.BooleanField(default=True)
    stock_alerts = models.BooleanField(default=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"

    @classmethod
    def get_or_create_preferences(cls, user):
        return cls.objects.get_or_create(
            user=user,
            defaults={field.name: True for field in cls._meta.fields if isinstance(field, models.BooleanField)}
        )

def create_notification(user, title, message, category, content_object=None):
    """Utility function to create notifications"""
    return Notification.objects.create(
        recipient=user,
        title=title,
        message=message,
        category=category,
        content_object=content_object
    )

