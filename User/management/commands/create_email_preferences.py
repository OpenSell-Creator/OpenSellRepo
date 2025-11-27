from django.core.management.base import BaseCommand
from User.utils import ensure_all_users_have_email_preferences

class Command(BaseCommand):
    help = 'Create email preferences for users who don\'t have them'

    def handle(self, *args, **kwargs):
        self.stdout.write('Creating missing email preferences...')
        
        created = ensure_all_users_have_email_preferences()
        
        if created > 0:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created email preferences for {created} users')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✓ All users already have email preferences')
            )