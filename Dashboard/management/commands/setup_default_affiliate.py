from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Dashboard.models import AffiliateProfile


class Command(BaseCommand):
    help = 'Create default "opensell" affiliate account'
    
    def handle(self, *args, **options):
        """Create default affiliate for non-referred users"""
        
        # Check if opensell user exists
        try:
            opensell_user = User.objects.get(username='opensell')
        except User.DoesNotExist:
            # Create opensell user
            opensell_user = User.objects.create_user(
                username='opensell',
                email='support@opensell.online',
                password=''.join([str(i) for i in range(10)])  # Random password
            )
            opensell_user.is_active = True
            opensell_user.save()
            self.stdout.write(self.style.SUCCESS('✓ Created opensell user'))
        
        # Check if affiliate profile exists
        try:
            affiliate = AffiliateProfile.objects.get(referral_code__iexact='opensell')
            self.stdout.write(self.style.WARNING('⚠️ Default affiliate already exists'))
            
            # Update to active if needed
            if affiliate.status != 'active':
                affiliate.status = 'active'
                affiliate.save()
                self.stdout.write(self.style.SUCCESS('✓ Activated default affiliate'))
            
        except AffiliateProfile.DoesNotExist:
            # Create affiliate profile
            affiliate = AffiliateProfile.objects.create(
                user=opensell_user,
                referral_code='opensell',
                status='active',  # Pre-approved
                funding_commission_rate=0,  # No commission for default
                boost_commission_rate=0,
                subscription_commission_rate=0,
                application_reason='Default system affiliate for non-referred users'
            )
            self.stdout.write(self.style.SUCCESS('✓ Created default affiliate profile'))
        
        # Display info
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== DEFAULT AFFILIATE SETUP COMPLETE ==='))
        self.stdout.write(f'Username: {opensell_user.username}')
        self.stdout.write(f'Referral Code: {affiliate.referral_code}')
        self.stdout.write(f'Status: {affiliate.status}')
        self.stdout.write(f'Commission Rates: {affiliate.funding_commission_rate}% (all 0 for default)')
        self.stdout.write('')
        self.stdout.write('Users who register without a referral code will be assigned to this affiliate.')
