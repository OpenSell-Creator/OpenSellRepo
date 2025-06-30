from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import AccountStatus, UserAccount

@receiver(post_save, sender=User)
def create_user_account(sender, instance, created, **kwargs):
    if created:
        free_status = AccountStatus.objects.filter(tier_type='free').first()
        UserAccount.objects.create(user=instance, status=free_status)
