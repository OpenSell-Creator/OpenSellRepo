from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Location

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a Profile instance with associated Location when a new User is created"""
    if created:
        # Create Location instance first
        location = Location.objects.create()
        
        # Create Profile with the location
        Profile.objects.create(user=instance, location=location)

@receiver(post_save, sender=Profile)
def create_profile_location(sender, instance, created, **kwargs):
    """Create a Location instance when a new Profile is created"""
    if created and not instance.location:
        # Create Location instance
        location = Location.objects.create(
            address='',  # Default empty address
            address_2='',  # Default empty address_2
        )
        # Associate Location with Profile
        instance.location = location
        # Save without triggering the signal again
        instance.save(update_fields=['location'])