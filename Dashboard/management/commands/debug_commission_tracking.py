from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Dashboard.models import (
    UserAccount, Transaction, Referral, 
    AffiliateProfile, AffiliateCommission
)
from decimal import Decimal
from django.db.models.signals import post_save
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Debug commission tracking issues'
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Test with specific username',
        )
        parser.add_argument(
            '--create-test',
            action='store_true',
            help='Create a test deposit',
        )
    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('='*80))
        self.stdout.write(self.style.WARNING('COMMISSION TRACKING DEBUG'))
        self.stdout.write(self.style.WARNING('='*80))
        
        # Step 1: Check if signal is connected
        self.check_signal_connection()
        
        # Step 2: Check for referrals
        self.check_referrals()
        
        # Step 3: Check affiliate status
        self.check_affiliate_status()
        
        # Step 4: Check recent transactions
        self.check_recent_transactions()
        
        # Step 5: Test with specific user or create test
        if options['username']:
            self.test_specific_user(options['username'], options['create_test'])
        elif options['create_test']:
            self.stdout.write(self.style.ERROR('\n❌ --create-test requires --username'))
    
    def check_signal_connection(self):
        """Check if the post_save signal is properly connected"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('1. CHECKING SIGNAL CONNECTION')
        self.stdout.write('='*80)
        
        # Get all receivers for Transaction post_save signal
        from django.db.models.signals import post_save
        from Dashboard.models import Transaction
        
        receivers = post_save._live_receivers(Transaction)
        
        self.stdout.write(f'\nSignal receivers for Transaction.post_save: {len(receivers)}')
        
        found_commission_handler = False
        for receiver in receivers:
            receiver_name = receiver.__name__ if hasattr(receiver, '__name__') else str(receiver)
            self.stdout.write(f'  - {receiver_name}')
            if 'commission' in receiver_name.lower() or 'affiliate' in receiver_name.lower():
                found_commission_handler = True
                self.stdout.write(self.style.SUCCESS('    ✓ Commission handler found!'))
        
        if not found_commission_handler:
            self.stdout.write(self.style.ERROR('\n❌ CRITICAL: Commission tracking signal NOT connected!'))
            self.stdout.write(self.style.WARNING('\nFIX: Ensure models.py has this at the bottom:'))
            self.stdout.write('''
@receiver(post_save, sender=Transaction)
def track_affiliate_commission(sender, instance, created, **kwargs):
    ...
            ''')
        else:
            self.stdout.write(self.style.SUCCESS('\n✓ Signal handler is connected'))
    
    def check_referrals(self):
        """Check referral records"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('2. CHECKING REFERRALS')
        self.stdout.write('='*80)
        
        total_referrals = Referral.objects.count()
        active_referrals = Referral.objects.filter(status='active').count()
        pending_referrals = Referral.objects.filter(status='pending').count()
        
        self.stdout.write(f'\nTotal referrals: {total_referrals}')
        self.stdout.write(f'Active referrals: {active_referrals}')
        self.stdout.write(f'Pending referrals: {pending_referrals}')
        
        if pending_referrals > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {pending_referrals} referrals still pending'))
            self.stdout.write('These will activate on first N1,000+ transaction\n')
            
            # Show sample pending referrals
            pending = Referral.objects.filter(status='pending')[:5]
            for ref in pending:
                self.stdout.write(f'  - {ref.referred_user.username} (by {ref.affiliate.referral_code})')
        
        if total_referrals == 0:
            self.stdout.write(self.style.ERROR('\n❌ NO REFERRALS FOUND!'))
            self.stdout.write('Users must be referred to earn commissions')
    
    def check_affiliate_status(self):
        """Check affiliate statuses"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('3. CHECKING AFFILIATE STATUS')
        self.stdout.write('='*80)
        
        affiliates = AffiliateProfile.objects.all()
        
        status_counts = {}
        for affiliate in affiliates:
            status = affiliate.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        self.stdout.write(f'\nTotal affiliates: {affiliates.count()}')
        for status, count in status_counts.items():
            color = self.style.SUCCESS if status == 'active' else self.style.WARNING
            self.stdout.write(color(f'  {status}: {count}'))
        
        inactive_count = sum(count for status, count in status_counts.items() if status != 'active')
        if inactive_count > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠️  {inactive_count} affiliates are NOT active'))
            self.stdout.write('Only ACTIVE affiliates earn commissions\n')
            
            # Show inactive affiliates
            inactive = AffiliateProfile.objects.exclude(status='active')[:5]
            for aff in inactive:
                self.stdout.write(f'  - {aff.referral_code} ({aff.status})')
    
    def check_recent_transactions(self):
        """Check recent transactions and their commission status"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('4. CHECKING RECENT TRANSACTIONS')
        self.stdout.write('='*80)
        
        from datetime import timedelta
        from django.utils import timezone
        
        recent_cutoff = timezone.now() - timedelta(hours=24)
        recent_txns = Transaction.objects.filter(
            created_at__gte=recent_cutoff,
            transaction_type__in=['deposit', 'boost_fee', 'subscription']
        ).order_by('-created_at')[:10]
        
        self.stdout.write(f'\nRecent qualifying transactions (last 24h): {recent_txns.count()}\n')
        
        for txn in recent_txns:
            self.stdout.write('-'*80)
            self.stdout.write(f'\nTransaction #{txn.id}:')
            self.stdout.write(f'  User: {txn.account.user.username}')
            self.stdout.write(f'  Type: {txn.transaction_type}')
            self.stdout.write(f'  Amount: N{txn.amount:,.2f}')
            self.stdout.write(f'  Date: {txn.created_at}')
            
            # Check if user has referral
            try:
                referral = Referral.objects.get(referred_user=txn.account.user)
                self.stdout.write(self.style.SUCCESS(f'  ✓ Referral exists: {referral.affiliate.referral_code}'))
                self.stdout.write(f'    Status: {referral.status}')
                self.stdout.write(f'    Affiliate status: {referral.affiliate.status}')
                
                # Check if commission was created
                commission = AffiliateCommission.objects.filter(
                    source_transaction=txn
                ).first()
                
                if commission:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Commission created: N{commission.commission_amount:,.2f}'))
                    self.stdout.write(f'    Status: {commission.status}')
                else:
                    self.stdout.write(self.style.ERROR('  ❌ NO COMMISSION CREATED'))
                    
                    # Diagnose why
                    reasons = []
                    if txn.amount < 1000:
                        reasons.append(f'Amount below minimum (N{txn.amount} < N1,000)')
                    if referral.affiliate.status != 'active':
                        reasons.append(f'Affiliate not active ({referral.affiliate.status})')
                    
                    if reasons:
                        self.stdout.write(self.style.WARNING(f'  Reasons: {", ".join(reasons)}'))
                    else:
                        self.stdout.write(self.style.ERROR('  ❌ UNKNOWN REASON - Signal may not be firing!'))
                        
            except Referral.DoesNotExist:
                self.stdout.write(self.style.WARNING('  ⚠️  No referral (user not referred)'))
    
    def test_specific_user(self, username, create_test):
        """Test commission tracking with specific user"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write(f'5. TESTING USER: {username}')
        self.stdout.write('='*80)
        
        try:
            user = User.objects.get(username=username)
            account = user.account
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ User "{username}" not found'))
            return
        except UserAccount.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ User "{username}" has no account'))
            return
        
        # Check referral
        try:
            referral = Referral.objects.get(referred_user=user)
            self.stdout.write(f'\n✓ Referral exists:')
            self.stdout.write(f'  Affiliate: {referral.affiliate.referral_code}')
            self.stdout.write(f'  Affiliate status: {referral.affiliate.status}')
            self.stdout.write(f'  Referral status: {referral.status}')
            self.stdout.write(f'  Total revenue: N{referral.total_revenue_generated:,.2f}')
            self.stdout.write(f'  Total commission: N{referral.total_commission_earned:,.2f}')
            
            affiliate = referral.affiliate
            
        except Referral.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'\n❌ User "{username}" has no referral'))
            self.stdout.write('This user cannot generate commissions')
            return
        
        # Show existing commissions
        commissions = AffiliateCommission.objects.filter(
            referral=referral
        ).order_by('-created_at')[:5]
        
        self.stdout.write(f'\nExisting commissions: {commissions.count()}')
        for comm in commissions:
            self.stdout.write(f'  - N{comm.commission_amount:,.2f} ({comm.status}) - {comm.created_at}')
        
        # Create test deposit if requested
        if create_test:
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('CREATING TEST DEPOSIT')
            self.stdout.write('-'*80)
            
            test_amount = Decimal('5000.00')
            
            self.stdout.write(f'\nBefore deposit:')
            self.stdout.write(f'  Account balance: N{account.balance:,.2f}')
            self.stdout.write(f'  Affiliate available: N{affiliate.available_balance:,.2f}')
            
            # Create deposit
            txn = Transaction.objects.create(
                account=account,
                amount=test_amount,
                transaction_type='deposit',
                description='DEBUG: Test deposit for commission tracking'
            )
            
            self.stdout.write(f'\n✓ Test deposit created: Transaction #{txn.id}')
            self.stdout.write(f'  Amount: N{txn.amount:,.2f}')
            
            # Wait a moment for signal to process
            import time
            time.sleep(0.5)
            
            # Check if commission was created
            commission = AffiliateCommission.objects.filter(
                source_transaction=txn
            ).first()
            
            # Refresh balances
            account.refresh_from_db()
            affiliate.refresh_from_db()
            
            self.stdout.write(f'\nAfter deposit:')
            self.stdout.write(f'  Account balance: N{account.balance:,.2f}')
            self.stdout.write(f'  Affiliate available: N{affiliate.available_balance:,.2f}')
            
            if commission:
                self.stdout.write(self.style.SUCCESS(f'\n✓ SUCCESS! Commission tracked:'))
                self.stdout.write(f'  Amount: N{commission.commission_amount:,.2f}')
                self.stdout.write(f'  Rate: {commission.commission_rate}%')
                self.stdout.write(f'  Status: {commission.status}')
                
                # Check if referral was activated
                referral.refresh_from_db()
                if referral.status == 'active':
                    self.stdout.write(self.style.SUCCESS(f'  ✓ Referral activated!'))
                    
            else:
                self.stdout.write(self.style.ERROR('\n❌ FAILED: No commission created!'))
                self.stdout.write('\nChecking logs...')
                
                # Check Django logs
                self.stdout.write(self.style.WARNING('\nLook for these messages in your Django logs:'))
                self.stdout.write('  - "SUCCESS INSTANT COMMISSION TRACKED"')
                self.stdout.write('  - "Skipping commission - ..."')
                self.stdout.write('  - "WARNING Commission tracking error"')


class Command(BaseCommand):
    pass  # Use the above implementation