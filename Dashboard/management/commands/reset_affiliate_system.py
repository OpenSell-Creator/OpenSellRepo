# Dashboard/management/commands/reset_affiliate_system.py
"""
COMPLETE AFFILIATE SYSTEM RESET
Wipes all affiliate data and starts fresh

Run with: python manage.py reset_affiliate_system
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth.models import User
from Dashboard.models import (
    AffiliateProfile, Referral, AffiliateCommission, 
    AffiliateWithdrawal
)
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Reset entire affiliate system - DANGER: Deletes all affiliate data!'

    def add_arguments(self, parser):
        parser.add_argument(
            '--confirm',
            action='store_true',
            help='Confirm you want to delete ALL affiliate data',
        )
        parser.add_argument(
            '--keep-profiles',
            action='store_true',
            help='Keep affiliate profiles but clear their balances and history',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.ERROR('='*80))
        self.stdout.write(self.style.ERROR('⚠️  AFFILIATE SYSTEM RESET'))
        self.stdout.write(self.style.ERROR('='*80))
        
        # Show current data
        self.show_current_state()
        
        # Confirm deletion
        if not options['confirm']:
            self.stdout.write('\n' + self.style.ERROR('⚠️  THIS WILL DELETE:'))
            self.stdout.write('  - All referral records')
            self.stdout.write('  - All commission records')
            self.stdout.write('  - All withdrawal records')
            if not options['keep_profiles']:
                self.stdout.write('  - All affiliate profiles')
            else:
                self.stdout.write('  - Reset all affiliate balances to zero')
            
            self.stdout.write('\n' + self.style.WARNING('This action CANNOT be undone!'))
            self.stdout.write('\nTo proceed, run:')
            cmd = 'python manage.py reset_affiliate_system --confirm'
            if options['keep_profiles']:
                cmd += ' --keep-profiles'
            self.stdout.write(self.style.SUCCESS(f'  {cmd}'))
            return
        
        # Final confirmation
        self.stdout.write('\n' + self.style.ERROR('FINAL WARNING!'))
        self.stdout.write('Type "DELETE ALL AFFILIATE DATA" to proceed: ')
        
        import sys
        if sys.stdin.isatty():
            confirm = input()
        else:
            confirm = 'DELETE ALL AFFILIATE DATA'  # For automated scripts
        
        if confirm != 'DELETE ALL AFFILIATE DATA':
            self.stdout.write(self.style.SUCCESS('\n✓ Reset cancelled'))
            return
        
        # Perform reset
        self.perform_reset(options['keep_profiles'])
    
    def show_current_state(self):
        """Show current affiliate system state"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('CURRENT STATE')
        self.stdout.write('='*80)
        
        # Affiliate Profiles
        affiliates = AffiliateProfile.objects.all()
        total_pending = sum(float(a.pending_balance) for a in affiliates)
        total_available = sum(float(a.available_balance) for a in affiliates)
        total_earned = sum(float(a.total_earned) for a in affiliates)
        
        self.stdout.write(f'\nAffiliate Profiles: {affiliates.count()}')
        if affiliates.count() > 0:
            self.stdout.write(f'  Total pending balance: N{total_pending:,.2f}')
            self.stdout.write(f'  Total available balance: N{total_available:,.2f}')
            self.stdout.write(f'  Total earned: N{total_earned:,.2f}')
        
        # Referrals
        referrals = Referral.objects.all()
        self.stdout.write(f'\nReferrals: {referrals.count()}')
        if referrals.count() > 0:
            active = referrals.filter(status='active').count()
            pending = referrals.filter(status='pending').count()
            self.stdout.write(f'  Active: {active}')
            self.stdout.write(f'  Pending: {pending}')
        
        # Commissions
        commissions = AffiliateCommission.objects.all()
        self.stdout.write(f'\nCommissions: {commissions.count()}')
        if commissions.count() > 0:
            total_commission = sum(float(c.commission_amount) for c in commissions)
            self.stdout.write(f'  Total amount: N{total_commission:,.2f}')
        
        # Withdrawals
        withdrawals = AffiliateWithdrawal.objects.all()
        self.stdout.write(f'\nWithdrawals: {withdrawals.count()}')
        if withdrawals.count() > 0:
            pending_withdrawals = withdrawals.filter(status='pending').count()
            completed_withdrawals = withdrawals.filter(status='completed').count()
            self.stdout.write(f'  Pending: {pending_withdrawals}')
            self.stdout.write(f'  Completed: {completed_withdrawals}')
    
    def perform_reset(self, keep_profiles):
        """Execute the reset"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('STARTING RESET...')
        self.stdout.write('='*80)
        
        try:
            with transaction.atomic():
                # Step 1: Delete commissions
                self.stdout.write('\n1. Deleting commissions...')
                commission_count = AffiliateCommission.objects.count()
                AffiliateCommission.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ Deleted {commission_count} commissions'))
                
                # Step 2: Delete withdrawals
                self.stdout.write('\n2. Deleting withdrawals...')
                withdrawal_count = AffiliateWithdrawal.objects.count()
                AffiliateWithdrawal.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ Deleted {withdrawal_count} withdrawals'))
                
                # Step 3: Delete referrals
                self.stdout.write('\n3. Deleting referrals...')
                referral_count = Referral.objects.count()
                Referral.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f'   ✓ Deleted {referral_count} referrals'))
                
                # Step 4: Handle affiliate profiles
                if keep_profiles:
                    self.stdout.write('\n4. Resetting affiliate balances...')
                    affiliate_count = AffiliateProfile.objects.count()
                    AffiliateProfile.objects.all().update(
                        pending_balance=0,
                        available_balance=0,
                        total_earned=0,
                        total_withdrawn=0
                    )
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Reset {affiliate_count} affiliate balances'))
                else:
                    self.stdout.write('\n4. Deleting affiliate profiles...')
                    affiliate_count = AffiliateProfile.objects.count()
                    AffiliateProfile.objects.all().delete()
                    self.stdout.write(self.style.SUCCESS(f'   ✓ Deleted {affiliate_count} affiliate profiles'))
                
                # Success
                self.stdout.write('\n' + '='*80)
                self.stdout.write(self.style.SUCCESS('✓ RESET COMPLETE'))
                self.stdout.write('='*80)
                
                self.stdout.write('\nDeleted:')
                self.stdout.write(f'  - {commission_count} commissions')
                self.stdout.write(f'  - {withdrawal_count} withdrawals')
                self.stdout.write(f'  - {referral_count} referrals')
                if keep_profiles:
                    self.stdout.write(f'  - Reset {affiliate_count} affiliate balances')
                else:
                    self.stdout.write(f'  - {affiliate_count} affiliate profiles')
                
                logger.info(
                    f'Affiliate system reset: {commission_count} commissions, '
                    f'{withdrawal_count} withdrawals, {referral_count} referrals, '
                    f'{affiliate_count} profiles deleted'
                )
                
                # Show next steps
                self.show_next_steps(keep_profiles)
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {str(e)}'))
            logger.error(f'Affiliate reset failed: {str(e)}', exc_info=True)
            raise
    
    def show_next_steps(self, kept_profiles):
        """Show what to do next"""
        self.stdout.write('\n' + '='*80)
        self.stdout.write('NEXT STEPS')
        self.stdout.write('='*80)
        
        if not kept_profiles:
            self.stdout.write('\n1. Create default affiliate (your platform account):')
            self.stdout.write('   python manage.py shell')
            self.stdout.write('')
            self.stdout.write('   >>> from django.contrib.auth.models import User')
            self.stdout.write('   >>> from Dashboard.models import AffiliateProfile')
            self.stdout.write('   >>> admin = User.objects.get(username="admin")  # Change username')
            self.stdout.write('   >>> aff = AffiliateProfile.objects.create(')
            self.stdout.write('   ...     user=admin,')
            self.stdout.write('   ...     referral_code="opensell",')
            self.stdout.write('   ...     status="active"')
            self.stdout.write('   ... )')
            self.stdout.write('')
        
        self.stdout.write('\n2. Test commission tracking:')
        self.stdout.write('   python manage.py debug_commission_tracking')
        
        self.stdout.write('\n3. Users can now apply to become affiliates at:')
        self.stdout.write('   /dashboard/affiliate/apply/')
        
        self.stdout.write('\n4. Approve affiliate applications in Django admin:')
        self.stdout.write('   Dashboard > Affiliate Profiles > Actions > Approve')
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('System is ready for new affiliate activity!'))
        self.stdout.write('='*80 + '\n')