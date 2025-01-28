from django.db import models
from django.contrib.auth.models import User
from .utils import user_directory_path
from django.db.models import Avg

# Create your models here.
class location(models.Model):
     address = models.CharField(max_length =120)
     address_2 = models.CharField(max_length = 120, blank= True)
     state = models.CharField(max_length= 50, blank=True)
     district = models.CharField(max_length= 50)
     
     def __str__(self) -> str:
        return f'location {self.id}'
 

class Profile(models.Model):
    user = models.OneToOneField( User, on_delete=models.CASCADE)
    photo = models.ImageField(upload_to= user_directory_path , null=True)
    bio = models.CharField(max_length=225, blank =True)
    phone_number = models.CharField(max_length=12, blank= True)
    location = models.OneToOneField(
         location,on_delete=models.SET_NULL,null=True)
    
    def __str__(self):
     return f'{self.user.username}'

def save(self, *args, **kwargs):
    # Delete old file when updating
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
   
    
    
    
