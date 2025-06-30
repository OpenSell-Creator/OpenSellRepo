from django.core.management.base import BaseCommand
from django_q.models import Schedule


class Command(BaseCommand):
    help = 'Set up Django-Q scheduled tasks'

    def handle(self, *args, **options):
        # Schedule to deactivate expired boosts - runs every hour
        schedule, created = Schedule.objects.get_or_create(
            name='Deactivate Expired Boosts',
            defaults={
                'func': 'Dashboard.tasks.deactivate_expired_boosts',
                'schedule_type': Schedule.CRON,
                'cron': '0 * * * *',  # Every hour at minute 0
                'repeats': -1,  # Repeat indefinitely
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Deactivate Expired Boosts')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Schedule already exists: Deactivate Expired Boosts')
            )

        # Schedule to check subscription renewals - runs daily at 9 AM
        schedule, created = Schedule.objects.get_or_create(
            name='Check Subscription Renewals',
            defaults={
                'func': 'Dashboard.tasks.check_subscription_renewals',
                'schedule_type': Schedule.CRON,
                'cron': '0 9 * * *',  # Daily at 9:00 AM
                'repeats': -1,  # Repeat indefinitely
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Check Subscription Renewals')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Schedule already exists: Check Subscription Renewals')
            )

        # Schedule to send subscription expiry warnings - runs daily at 10 AM
        schedule, created = Schedule.objects.get_or_create(
            name='Send Subscription Expiry Warnings',
            defaults={
                'func': 'Dashboard.tasks.send_subscription_expiry_warnings',
                'schedule_type': Schedule.CRON,
                'cron': '0 10 * * *',  # Daily at 10:00 AM
                'repeats': -1,  # Repeat indefinitely
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Send Subscription Expiry Warnings')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Schedule already exists: Send Subscription Expiry Warnings')
            )

        # Schedule to cleanup old tasks - runs weekly on Sunday at midnight
        schedule, created = Schedule.objects.get_or_create(
            name='Cleanup Old Tasks',
            defaults={
                'func': 'Dashboard.tasks.cleanup_old_tasks',
                'schedule_type': Schedule.CRON,
                'cron': '0 0 * * 0',  # Weekly on Sunday at midnight
                'repeats': -1,  # Repeat indefinitely
            }
        )
        if created:
            self.stdout.write(
                self.style.SUCCESS('✓ Created schedule: Cleanup Old Tasks')
            )
        else:
            self.stdout.write(
                self.style.WARNING('⚠ Schedule already exists: Cleanup Old Tasks')
            )

        self.stdout.write(
            self.style.SUCCESS('\n✅ All schedules have been set up successfully!')
        )