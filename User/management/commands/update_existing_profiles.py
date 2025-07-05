from django.core.management.base import BaseCommand
from User.models import Profile

class Command(BaseCommand):
    help = 'Update existing profiles with default business verification status'

    def handle(self, *args, **options):
        # Update all existing profiles to have unverified status
        updated = Profile.objects.filter(
            business_verification_status__isnull=True
        ).update(business_verification_status='unverified')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully updated {updated} profiles with default verification status'
            )
        )
