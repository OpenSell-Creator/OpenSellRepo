from django.core.management.base import BaseCommand
from Dashboard.models import AccountStatus

class Command(BaseCommand):
    help = 'Setup default account tiers (Free and Pro)'

    def handle(self, *args, **options):
        # Create Free tier
        free_tier, created = AccountStatus.objects.get_or_create(
            tier_type='free',
            defaults={
                'name': 'Free User',
                'description': 'Basic free account with limited features',
                'benefits': 'Basic listing features, 5 listings maximum',
                'monthly_price': 0.00,
                'yearly_price': 0.00,
                'max_listings': 5,
                'listing_discount': 0.00,
                'boost_discount': 0.00,
                'featured_listings': 0,
                'priority_support': False,
                'analytics_access': False,
                'min_balance': 0.00
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created Free tier: {free_tier.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠ Free tier already exists: {free_tier.name}')
            )

        # Create Pro tier
        pro_tier, created = AccountStatus.objects.get_or_create(
            tier_type='pro',
            defaults={
                'name': 'Pro User',
                'description': 'Premium subscription with advanced features',
                'benefits': 'Unlimited listings, 30% boost discount, priority support, analytics access',
                'monthly_price': 2000.00,
                'yearly_price': 20000.00,
                'max_listings': 999999,
                'listing_discount': 0.00,
                'boost_discount': 30.00,
                'featured_listings': 2,
                'priority_support': True,
                'analytics_access': True,
                'min_balance': 0.00
            }
        )
        
        if created:
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created Pro tier: {pro_tier.name}')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'⚠ Pro tier already exists: {pro_tier.name}')
            )

        self.stdout.write(
            self.style.SUCCESS('Account tiers setup completed successfully!')
        )
        