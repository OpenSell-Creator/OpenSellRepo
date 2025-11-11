# Dashboard/management/commands/migrate_instant_commissions.py
"""
Management command to migrate existing affiliate commissions to instant availability
Run with: python manage.py migrate_instant_commissions
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from Dashboard.models import AffiliateCommission, AffiliateProfile
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate pending commissions to instantly available (removes 30-day hold)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']
        
        self.stdout.write(self.style.WARNING('='*70))
        self.stdout.write(self.style.WARNING('AFFILIATE COMMISSION MIGRATION'))
        self.stdout.write(self.style.WARNING('='*70))
        
        # Get statistics
        total_commissions = AffiliateCommission.objects.count()
        pending_commissions = AffiliateCommission.objects.filter(status='pending')
        pending_count = pending_commissions.count()
        
        if pending_count == 0:
            self.stdout.write(self.style.SUCCESS('\n✓ No pending commissions to migrate!'))
            self.stdout.write(self.style.SUCCESS('All commissions are already available.'))
            return
        
        # Calculate total amount
        total_pending_amount = sum(c.commission_amount for c in pending_commissions)
        
        self.stdout.write(f'\nTotal commissions: {total_commissions}')
        self.stdout.write(self.style.WARNING(f'Pending commissions: {pending_count}'))
        self.stdout.write(self.style.WARNING(f'Total pending amount: N{total_pending_amount:,.2f}'))
        
        # Show affected affiliates
        affected_affiliates = pending_commissions.values_list(
            'affiliate__referral_code', 
            flat=True
        ).distinct()
        
        self.stdout.write(f'\nAffected affiliates: {len(affected_affiliates)}')
        for code in list(affected_affiliates)[:10]:
            self.stdout.write(f'  - {code}')
        if len(affected_affiliates) > 10:
            self.stdout.write(f'  ... and {len(affected_affiliates) - 10} more')
        
        if dry_run:
            self.stdout.write(self.style.SUCCESS('\n[DRY RUN] No changes made'))
            self._show_sample_changes(pending_commissions)
            return
        
        # Confirmation
        if not force:
            self.stdout.write('\n' + '='*70)
            self.stdout.write(self.style.WARNING('⚠️  THIS WILL:'))
            self.stdout.write('1. Change all pending commissions to "available"')
            self.stdout.write('2. Move pending_balance → available_balance for all affiliates')
            self.stdout.write('3. Update available_at timestamp to NOW')
            self.stdout.write('='*70 + '\n')
            
            confirm = input('Type "YES" to proceed: ')
            if confirm != 'YES':
                self.stdout.write(self.style.ERROR('\n❌ Migration cancelled'))
                return
        
        # Perform migration
        self.stdout.write('\n' + self.style.WARNING('Starting migration...'))
        
        try:
            with transaction.atomic():
                migrated_count = 0
                migrated_amount = Decimal('0')
                updated_affiliates = set()
                
                for commission in pending_commissions:
                    # Update commission
                    commission.status = 'available'
                    commission.available_at = timezone.now()
                    commission.save(update_fields=['status', 'available_at'])
                    
                    migrated_count += 1
                    migrated_amount += commission.commission_amount
                    updated_affiliates.add(commission.affiliate.id)
                    
                    if migrated_count % 50 == 0:
                        self.stdout.write(f'  Processed {migrated_count}/{pending_count}...')
                
                # Update affiliate balances
                self.stdout.write('\nUpdating affiliate balances...')
                
                for affiliate_id in updated_affiliates:
                    affiliate = AffiliateProfile.objects.get(id=affiliate_id)
                    
                    # Move all pending to available
                    amount_to_move = affiliate.pending_balance
                    affiliate.available_balance += amount_to_move
                    affiliate.pending_balance = Decimal('0')
                    affiliate.save(update_fields=['pending_balance', 'available_balance'])
                    
                    self.stdout.write(
                        f'  ✓ {affiliate.referral_code}: '
                        f'Moved N{amount_to_move:,.2f} to available'
                    )
                
                # Success summary
                self.stdout.write('\n' + '='*70)
                self.stdout.write(self.style.SUCCESS('✓ MIGRATION COMPLETE'))
                self.stdout.write('='*70)
                self.stdout.write(f'Migrated commissions: {migrated_count}')
                self.stdout.write(f'Total amount: N{migrated_amount:,.2f}')
                self.stdout.write(f'Updated affiliates: {len(updated_affiliates)}')
                
                logger.info(
                    f'Commission migration complete: {migrated_count} commissions, '
                    f'N{migrated_amount:.2f}, {len(updated_affiliates)} affiliates'
                )
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ ERROR: {str(e)}'))
            logger.error(f'Commission migration failed: {str(e)}', exc_info=True)
            raise
    
    def _show_sample_changes(self, pending_commissions):
        """Show sample of what would be changed"""
        self.stdout.write('\nSample changes (first 5):')
        self.stdout.write('-'*70)
        
        for commission in pending_commissions[:5]:
            self.stdout.write(
                f'\nCommission #{commission.id}:\n'
                f'  Affiliate: {commission.affiliate.referral_code}\n'
                f'  Amount: N{commission.commission_amount:,.2f}\n'
                f'  Status: {commission.status} → available\n'
                f'  Available: {commission.available_at} → NOW'
            )
        
        if pending_commissions.count() > 5:
            self.stdout.write(f'\n... and {pending_commissions.count() - 5} more')
            