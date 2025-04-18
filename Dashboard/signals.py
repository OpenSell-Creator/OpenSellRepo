from django.contrib.auth.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Product_Listing
from .models import AccountStatus, UserAccount

@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        # Get default status
        default_status = AccountStatus.objects.filter(min_balance=0).first()
        UserAccount.objects.create(user=instance, status=default_status)