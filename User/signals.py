from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Location
from .models import Profile, EmailPreferences

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Create a Profile instance with associated Location when a new User is created"""
    if created:
        try:
            # Try to create Location instance
            location = Location.objects.create(
                address='',
                address_2='',
                city=''  # Make sure city is explicitly included
            )
            
            # Create Profile with the location
            Profile.objects.create(user=instance, location=location)
        except Exception as e:
            # Fall back to creating just a profile if location creation fails
            print(f"Error creating location: {e}")
            Profile.objects.create(user=instance)

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
        
        
@receiver(post_save, sender=Profile)
def create_email_preferences(sender, instance, created, **kwargs):
    if created:
        EmailPreferences.objects.create(profile=instance)

