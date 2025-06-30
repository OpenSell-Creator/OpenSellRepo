from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Dashboard.models import UserAccount, AccountStatus

class Command(BaseCommand):
    help = 'Fix accounts without proper status and create missing accounts'

    def handle(self, *args, **options):
        # Ensure free status exists
        free_status, created = AccountStatus.objects.get_or_create(
            tier_type='free',
            defaults={
                'name': 'Free User',
                'description': 'Basic free account',
                'max_listings': 5,
                'monthly_price': 0,
                'yearly_price': 0,
                'boost_discount': 0,
                'listing_discount': 0
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created free status')
            )

        # Ensure pro status exists
        pro_status, created = AccountStatus.objects.get_or_create(
            tier_type='pro',
            defaults={
                'name': 'Pro User',
                'description': 'Premium subscription account',
                'max_listings': 999999,
                'monthly_price': 2000,
                'yearly_price': 20000,
                'boost_discount': 30,
                'listing_discount': 0
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS('Created pro status')
            )

        # Fix accounts without status
        accounts_fixed = 0
        accounts_without_status = UserAccount.objects.filter(status__isnull=True)
        for account in accounts_without_status:
            account.status = free_status
            account.save()
            accounts_fixed += 1

        # Create accounts for users without accounts
        accounts_created = 0
        users_without_accounts = User.objects.filter(account__isnull=True)
        for user in users_without_accounts:
            UserAccount.objects.create(user=user, status=free_status)
            accounts_created += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully fixed {accounts_fixed} accounts and created {accounts_created} new accounts'
            )
        )