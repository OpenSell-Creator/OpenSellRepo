from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from .utils import user_directory_path
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from django.db import models
from django.utils.crypto import get_random_string
from django.urls import reverse
from django.db.models import Avg
import random


# Create your models here.
class State(models.Model):
    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        ordering = ['name']

class LGA(models.Model):
    name = models.CharField(max_length=100)
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name='lgas')  # Removed trailing comma
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.name}, {self.state.name}"
    
    class Meta:
        ordering = ['name']
        unique_together = ['name', 'state']

class Location(models.Model):
    address = models.CharField(max_length=120, blank=True, null=True)
    address_2 = models.CharField(max_length=120, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)  # New field
    state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True)
    lga = models.ForeignKey(LGA, on_delete=models.SET_NULL, null=True, blank=True)
    
    def __str__(self):
        location_parts = []
        if self.address:
            location_parts.append(self.address)
        if self.city:
            location_parts.append(self.city)
        if self.lga:
            location_parts.append(self.lga.name)
        if self.state:
            location_parts.append(self.state.name)
        
        if location_parts:
            return ', '.join(filter(None, location_parts))
        return "No location details provided" # Fallback for empty locations

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    photo = ProcessedImageField(
        upload_to=user_directory_path,
        processors=[ResizeToFill(200, 200)], 
        format='JPEG',
        options={'quality': 85},
        null=True
    )
    bio = models.CharField(max_length=225, blank=True)
    phone_number = models.CharField(max_length=11, blank=True)
    location = models.OneToOneField(
        Location, on_delete=models.SET_NULL, null=True
    )
    email_verified = models.BooleanField(default=False)
    email_otp = models.CharField(max_length=6, blank=True, null=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.user.username}'
    
    def get_or_create_email_preferences(self):
        """
        Get or create the email preferences for this profile
        
        Returns:
            EmailPreferences: The email preferences object for this profile
        """
        if hasattr(self, 'email_preferences'):
            return self.email_preferences
        
        # Create new preferences with default settings
        from .models import EmailPreferences  # Import here to avoid circular imports
        preferences = EmailPreferences.objects.create(profile=self)
        return preferences
    
    def save(self, *args, **kwargs):
        
        try:
            old = Profile.objects.get(pk=self.pk)
            if old.photo and old.photo != self.photo:
                old.photo.delete(save=False)
        except Profile.DoesNotExist:
            pass
        is_new = self.pk is None
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        if self.photo:
            self.photo.delete(save=False)
        super().delete(*args, **kwargs)
    
    @property
    def average_rating(self):
        return self.seller_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    def generate_otp(self):
        """Generate a 6-digit OTP for email verification"""
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.email_otp = otp
        self.otp_created_at = timezone.now()
        self.save()
        return otp
    
    def is_otp_valid(self):
        """Check if the OTP is still valid (within 10 minutes)"""
        if not self.otp_created_at:
            return False
        
        time_diff = timezone.now() - self.otp_created_at
        return time_diff.total_seconds() < 600  # 10 minutes

class EmailPreferences(models.Model):
    """Model to store user email preferences"""
    profile = models.OneToOneField('Profile', on_delete=models.CASCADE, related_name='email_preferences')
    
    # Email categories
    receive_marketing = models.BooleanField(default=True, help_text="Marketing emails and newsletters")
    receive_announcements = models.BooleanField(default=True, help_text="Important announcements about OpenSell")
    receive_notifications = models.BooleanField(default=True, help_text="Activity notifications")
    
    # Unsubscribe token
    unsubscribe_token = models.CharField(max_length=64, unique=True, blank=True, null=True)
    token_created_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"Email preferences for {self.profile.user.username}"
    
    def save(self, *args, **kwargs):
        # Generate unsubscribe token if not present
        if not self.unsubscribe_token:
            self.unsubscribe_token = get_random_string(64)
            self.token_created_at = timezone.now()
        super().save(*args, **kwargs)
    
    def generate_new_token(self):
        """Generate a new unsubscribe token - use when security requires token rotation"""
        self.unsubscribe_token = get_random_string(64)
        self.token_created_at = timezone.now()
        self.save()
        return self.unsubscribe_token
    
    @property
    def is_completely_unsubscribed(self):
        """Check if user is unsubscribed from all non-essential emails"""
        return not (self.receive_marketing or self.receive_announcements or self.receive_notifications)
    
    def get_absolute_preferences_url(self):
        """Get the URL for managing email preferences"""
        return reverse('email_preferences') + f"?user={self.profile.user.id}&token={self.unsubscribe_token}"