from django.db import models
from django.contrib.auth.models import User
from .utils import user_directory_path
from imagekit.models import ProcessedImageField
from imagekit.processors import ResizeToFill
from django.db.models import Avg


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
    user = models.OneToOneField( User, on_delete=models.CASCADE)
    photo = ProcessedImageField(
        upload_to=user_directory_path,
        processors=[ResizeToFill(300, 300)], 
        format='JPEG',
        options={'quality': 85},
        null=True
    )
    bio = models.CharField(max_length=225, blank =True)
    phone_number = models.CharField(max_length=11, blank= True)
    location = models.OneToOneField(
         Location,on_delete=models.SET_NULL,null=True)
    
    def __str__(self):
     return f'{self.user.username}'
 

def save(self, *args, **kwargs):
    try:
        old = Profile.objects.get(pk=self.pk)
        if old.photo and old.photo != self.photo:
            old.photo.delete(save=False)
    except Profile.DoesNotExist:
        pass
    super().save(*args, **kwargs)


def delete(self, *args, **kwargs):
    if self.photo:
        self.photo.delete(save=False)
    super().delete(*args, **kwargs)
 
    @property
    def average_rating(self):
        return self.seller_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
   
    
    
    
