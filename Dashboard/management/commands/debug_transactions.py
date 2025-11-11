from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from Dashboard.models import (
    UserAccount, Transaction, AffiliateProfile, 
    Referral, AffiliateCommission
)
from decimal import Decimal

class Command(BaseCommand):
    help = 'Debug transaction and commission issues'

    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Specific username to check',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Attempt to fix balance discrepancies',
        )

    def handle(self, *args, **options):
        username = options.get('username')
        should_fix = options.get('fix', False)
        
        self.stdout.write(self.style.SUCCESS('\n=== Transaction & Commission Debug Report ===\n'))
        
        if username:
            users = User.objects.filter(username=username)
            if not users.exists():
                self.stdout.write(self.style.ERROR(f'User "{username}" not found'))
                return
        else:
            # Check all users with transactions
            users = User.objects.filter(account__transactions__isnull=False).distinct()
        
        for user in users:
            self.check_user(user, should_fix)
        
        self.stdout.write(self.style.SUCCESS('\n=== End of Report ===\n'))

    def check_user(self, user, should_fix=False):
        """Check a specific user's transactions and balance"""
        try:
            account = user.account
        except UserAccount.DoesNotExist:
            self.stdout.write(self.style.WARNING(f'⚠️  {user.username}: No account found'))
            return
        
        self.stdout.write(self.style.HTTP_INFO(f'\n--- Checking {user.username} ---'))
        
        # Get all transactions
        transactions = Transaction.objects.filter(account=account).order_by('created_at')
        
        # Calculate expected balance
        calculated_balance = Decimal('0')
        for txn in transactions:
            calculated_balance += txn.amount
            self.stdout.write(
                f"  {txn.created_at.strftime('%Y-%m-%d %H:%M')} | "
                f"{txn.transaction_type:15} | "
                f"Amount: {txn.amount:10.2f} | "
                f"Running: {calculated_balance:10.2f}"
            )
        
        # Compare with actual balance
        self.stdout.write(f'\nCalculated Balance: ₦{calculated_balance:,.2f}')
        self.stdout.write(f'Actual Balance:     ₦{account.balance:,.2f}')
        
        discrepancy = calculated_balance - account.balance
        if abs(discrepancy) > Decimal('0.01'):
            self.stdout.write(
                self.style.ERROR(f'❌ DISCREPANCY: ₦{discrepancy:,.2f}')
            )
            
            if should_fix:
                self.stdout.write(self.style.WARNING('Fixing balance...'))
                account.balance = calculated_balance
                account.save()
                self.stdout.write(self.style.SUCCESS('✓ Balance fixed!'))
        else:
            self.stdout.write(self.style.SUCCESS('✓ Balance matches!'))
        
        # Check if user is referred
        try:
            referral = Referral.objects.get(referred_user=user)
            self.check_referral_commissions(referral)
        except Referral.DoesNotExist:
            self.stdout.write('  Not a referred user')

    def check_referral_commissions(self, referral):
        """Check commissions for a referral"""
        self.stdout.write(f'\n  Referral Info:')
        self.stdout.write(f'    Affiliate: {referral.affiliate.referral_code}')
        self.stdout.write(f'    Status: {referral.status}')
        self.stdout.write(f'    First Transaction: {referral.first_qualifying_transaction}')
        
        # Get commissions
        commissions = AffiliateCommission.objects.filter(referral=referral)
        
        self.stdout.write(f'\n  Commissions ({commissions.count()}):')
        
        total_pending = Decimal('0')
        total_available = Decimal('0')
        total_paid = Decimal('0')
        
        for comm in commissions:
            self.stdout.write(
                f'    {comm.created_at.strftime("%Y-%m-%d")} | '
                f'{comm.transaction_type:12} | '
                f'Base: ₦{comm.base_amount:8.2f} | '
                f'Rate: {comm.commission_rate:5.2f}% | '
                f'Commission: ₦{comm.commission_amount:8.2f} | '
                f'Status: {comm.status}'
            )
            
            if comm.status == 'pending':
                total_pending += comm.commission_amount
            elif comm.status == 'available':
                total_available += comm.commission_amount
            elif comm.status == 'paid':
                total_paid += comm.commission_amount
        
        # Check affiliate balances
        affiliate = referral.affiliate
        
        self.stdout.write(f'\n  Affiliate Balance Check:')
        self.stdout.write(f'    Calculated Pending:   ₦{total_pending:,.2f}')
        self.stdout.write(f'    Actual Pending:       ₦{affiliate.pending_balance:,.2f}')
        self.stdout.write(f'    Calculated Available: ₦{total_available:,.2f}')
        self.stdout.write(f'    Actual Available:     ₦{affiliate.available_balance:,.2f}')
        self.stdout.write(f'    Total Earned:         ₦{affiliate.total_earned:,.2f}')
        
        # Check discrepancies
        pending_discrepancy = total_pending - affiliate.pending_balance
        available_discrepancy = total_available - affiliate.available_balance
        
        if abs(pending_discrepancy) > Decimal('0.01'):
            self.stdout.write(
                self.style.ERROR(f'    ❌ Pending Balance Discrepancy: ₦{pending_discrepancy:,.2f}')
            )
        
        if abs(available_discrepancy) > Decimal('0.01'):
            self.stdout.write(
                self.style.ERROR(f'    ❌ Available Balance Discrepancy: ₦{available_discrepancy:,.2f}')
            )