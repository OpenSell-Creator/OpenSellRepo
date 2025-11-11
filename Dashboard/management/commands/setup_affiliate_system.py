# Dashboard/management/commands/setup_affiliate_system.py
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from django.utils import timezone
from Dashboard.models import (
    AffiliateProfile, Referral, UserAccount, AccountStatus
)
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Setup affiliate system with default affiliate and optional test data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--admin-username',
            type=str,
            default='admin',
            help='Username for default affiliate (default: admin)',
        )
        parser.add_argument(
            '--create-test-data',
            action='store_true',
            help='Create test affiliate and referral for testing',
        )
        parser.add_argument(
            '--skip-default',
            action='store_true',
            help='Skip creating default "opensell" affiliate',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(self.style.SUCCESS('AFFILIATE SYSTEM SETUP'))
        self.stdout.write(self.style.SUCCESS('='*80))
        
        try:
            with transaction.atomic():
                # Step 1: Create default affiliate
                if not options['skip_default']:
                    self.create_default_affiliate(options['admin_username'])
                
                # Step 2: Create test data if requested
                if options['create_test_data']:
                    self.create_test_data()
                
                # Step 3: Verify signal connection
                self.verify_signal()
                
                # Success
                self.stdout.write('\n' + '='*80)
                self.stdout.write(self.style.SUCCESS('✓ SETUP COMPLETE'))
                self.stdout.write('='*80)
                self.show_summary()
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {str(e)}'))
            logger.error(f'Affiliate setup failed: {str(e)}', exc_info=True)
            raise
    
    def create_default_affiliate(self, admin_username):
        """Create default platform affiliate"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('1. CREATING DEFAULT AFFILIATE')
        self.stdout.write('='*80)
        
        # Get or create admin user
        try:
            admin_user = User.objects.get(username=admin_username)
            self.stdout.write(f'\n✓ Found admin user: {admin_username}')
        except User.DoesNotExist:
            self.stdout.write(f'\nAdmin user "{admin_username}" not found. Creating...')
            admin_user = User.objects.create_user(
                username=admin_username,
                email=f'{admin_username}@opensell.online',
                password='changeme123'
            )
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.save()
            self.stdout.write(self.style.WARNING(f'⚠️  Created admin user with password: changeme123'))
            self.stdout.write(self.style.WARNING('   CHANGE THIS PASSWORD IMMEDIATELY!'))
        
        # Create or update default affiliate
        affiliate, created = AffiliateProfile.objects.update_or_create(
            referral_code='opensell',
            defaults={
                'user': admin_user,
                'status': 'active',
                'funding_commission_rate': Decimal('5.0'),
                'boost_commission_rate': Decimal('10.0'),
                'subscription_commission_rate': Decimal('15.0'),
                'minimum_withdrawal': Decimal('5000.0'),
                'approved_at': timezone.now(),
                'approved_by': admin_user,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('\n✓ Created default affiliate:'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Updated default affiliate:'))
        
        self.stdout.write(f'  Referral code: {affiliate.referral_code}')
        self.stdout.write(f'  Status: {affiliate.status}')
        self.stdout.write(f'  User: {affiliate.user.username}')
        self.stdout.write(f'  Commission rates:')
        self.stdout.write(f'    - Funding: {affiliate.funding_commission_rate}%')
        self.stdout.write(f'    - Boost: {affiliate.boost_commission_rate}%')
        self.stdout.write(f'    - Subscription: {affiliate.subscription_commission_rate}%')
    
    def create_test_data(self):
        """Create test affiliate and referral"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('2. CREATING TEST DATA')
        self.stdout.write('='*80)
        
        # Create test affiliate
        self.stdout.write('\nCreating test affiliate...')
        test_aff_user, created = User.objects.get_or_create(
            username='test_affiliate',
            defaults={
                'email': 'test_affiliate@test.com',
                'first_name': 'Test',
                'last_name': 'Affiliate'
            }
        )
        if created:
            test_aff_user.set_password('test123')
            test_aff_user.save()
        
        test_affiliate, created = AffiliateProfile.objects.update_or_create(
            referral_code='testaff',
            defaults={
                'user': test_aff_user,
                'status': 'active',
                'funding_commission_rate': Decimal('5.0'),
                'boost_commission_rate': Decimal('10.0'),
                'subscription_commission_rate': Decimal('15.0'),
                'approved_at': timezone.now(),
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Test affiliate: {test_affiliate.referral_code}'))
        if created:
            self.stdout.write(f'    Password: test123')
        
        # Create test buyer
        self.stdout.write('\nCreating test buyer...')
        test_buyer, created = User.objects.get_or_create(
            username='test_buyer',
            defaults={
                'email': 'test_buyer@test.com',
                'first_name': 'Test',
                'last_name': 'Buyer'
            }
        )
        if created:
            test_buyer.set_password('test123')
            test_buyer.save()
        
        # Ensure UserAccount exists
        free_status, _ = AccountStatus.objects.get_or_create(
            tier_type='free',
            defaults={
                'name': 'Free User',
                'monthly_price': 0,
                'two_month_price': 0,
                'max_listings': 5,
            }
        )
        
        buyer_account, created = UserAccount.objects.get_or_create(
            user=test_buyer,
            defaults={
                'status': free_status,
                'balance': Decimal('0.00')
            }
        )
        
        # Add initial balance
        if created:
            buyer_account.balance = Decimal('20000.00')
            buyer_account.save()
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Test buyer: {test_buyer.username}'))
        self.stdout.write(f'    Balance: N{buyer_account.balance:,.2f}')
        if created:
            self.stdout.write(f'    Password: test123')
        
        # Create referral
        self.stdout.write('\nCreating referral relationship...')
        referral, created = Referral.objects.update_or_create(
            referred_user=test_buyer,
            defaults={
                'affiliate': test_affiliate,
                'referral_code_used': 'testaff',
                'status': 'active',
                'first_qualifying_transaction': timezone.now(),
            }
        )
        
        self.stdout.write(self.style.SUCCESS(f'  ✓ Referral created:'))
        self.stdout.write(f'    Buyer: {test_buyer.username}')
        self.stdout.write(f'    Referred by: {test_affiliate.referral_code}')
        self.stdout.write(f'    Status: {referral.status}')
        
        # Show test instructions
        self.stdout.write('\n' + '-'*80)
        self.stdout.write(self.style.SUCCESS('TEST INSTRUCTIONS:'))
        self.stdout.write('-'*80)
        self.stdout.write('\nTo test commission tracking, run:')
        self.stdout.write(self.style.WARNING('  python manage.py debug_commission_tracking --username test_buyer --create-test'))
        self.stdout.write('\nOr manually in shell:')
        self.stdout.write('  python manage.py shell')
        self.stdout.write('')
        self.stdout.write('  >>> from Dashboard.models import Transaction, UserAccount')
        self.stdout.write('  >>> from decimal import Decimal')
        self.stdout.write('  >>> account = UserAccount.objects.get(user__username="test_buyer")')
        self.stdout.write('  >>> txn = Transaction.objects.create(')
        self.stdout.write('  ...     account=account,')
        self.stdout.write('  ...     amount=Decimal("5000.00"),')
        self.stdout.write('  ...     transaction_type="deposit",')
        self.stdout.write('  ...     description="Test deposit"')
        self.stdout.write('  ... )')
        self.stdout.write('  >>> # Check if commission was created')
        self.stdout.write('  >>> from Dashboard.models import AffiliateCommission')
        self.stdout.write('  >>> AffiliateCommission.objects.filter(source_transaction=txn)')
    
    def verify_signal(self):
        """Verify signal is connected"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('3. VERIFYING SIGNAL CONNECTION')
        self.stdout.write('='*80)
        
        from django.db.models.signals import post_save
        from Dashboard.models import Transaction
        
        receivers = post_save._live_receivers(Transaction)
        
        self.stdout.write(f'\nTransaction.post_save receivers: {len(receivers)}')
        
        found = False
        for receiver in receivers:
            receiver_name = receiver.__name__ if hasattr(receiver, '__name__') else str(receiver)
            if 'commission' in receiver_name.lower():
                self.stdout.write(self.style.SUCCESS(f'  ✓ Found: {receiver_name}'))
                found = True
        
        if not found:
            self.stdout.write(self.style.ERROR('\n❌ WARNING: Commission signal handler not found!'))
            self.stdout.write(self.style.WARNING('\nEnsure Dashboard/models.py has:'))
            self.stdout.write('''
@receiver(post_save, sender=Transaction)
def track_affiliate_commission(sender, instance, created, **kwargs):
    ...
            ''')
            self.stdout.write(self.style.WARNING('\nThen restart Django server!'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Signal handler is connected'))
    
    def show_summary(self):
        """Show summary and next steps"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('SUMMARY')
        self.stdout.write('='*80)
        
        # Count everything
        affiliates = AffiliateProfile.objects.all()
        active_affiliates = affiliates.filter(status='active').count()
        referrals = Referral.objects.all()
        
        self.stdout.write(f'\nAffiliate Profiles: {affiliates.count()}')
        self.stdout.write(f'  Active: {active_affiliates}')
        self.stdout.write(f'\nReferrals: {referrals.count()}')
        
        # Show affiliate codes
        self.stdout.write('\nActive Affiliate Codes:')
        for aff in affiliates.filter(status='active'):
            self.stdout.write(f'  - {aff.referral_code} (@{aff.user.username})')
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write('NEXT STEPS')
        self.stdout.write('='*80)
        
        self.stdout.write('\n1. Share referral links:')
        self.stdout.write('   https://yourdomain.com/signup/?ref=opensell')
        
        self.stdout.write('\n2. Let users apply to become affiliates:')
        self.stdout.write('   /dashboard/affiliate/apply/')
        
        self.stdout.write('\n3. Approve affiliate applications in admin:')
        self.stdout.write('   Dashboard > Affiliate Profiles > Select > Actions > Approve')
        
        self.stdout.write('\n4. Test commission tracking:')
        self.stdout.write('   python manage.py debug_commission_tracking')
        
        self.stdout.write('\n' + '='*80)