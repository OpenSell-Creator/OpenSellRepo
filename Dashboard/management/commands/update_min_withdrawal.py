# Dashboard/management/commands/update_min_withdrawal.py
from django.core.management.base import BaseCommand
from Dashboard.models import AffiliateProfile

class Command(BaseCommand):
    help = 'Update minimum withdrawal amount for all affiliates'

    def handle(self, *args, **options):
        updated = AffiliateProfile.objects.filter(
            minimum_withdrawal=5000
        ).update(minimum_withdrawal=2000)
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated} affiliate profiles')
        )