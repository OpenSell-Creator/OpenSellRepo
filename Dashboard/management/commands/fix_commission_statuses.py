# Save as: Dashboard/management/commands/fix_commission_statuses.py

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from django.db.models import Count
from Dashboard.models import AffiliateCommission, AffiliateProfile
from decimal import Decimal

class Command(BaseCommand):
    help = 'Fix commission statuses from pending to available (instant payment system)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n=== Commission Status Fix Tool ===\n'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made\n'))
        
        # Find all "pending" commissions (should all be "available" in instant system)
        pending_commissions = AffiliateCommission.objects.filter(
            status='pending'
        ).select_related('affiliate', 'referral')
        
        total_count = pending_commissions.count()
        
        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('✓ No pending commissions found!'))
            self.stdout.write('All commissions are already set to "available" status.\n')
            return
        
        self.stdout.write(f'Found {total_count} pending commissions that should be available\n')
        
        # Group by affiliate for batch processing
        affiliate_changes = {}
        
        for commission in pending_commissions:
            affiliate_id = commission.affiliate.id
            
            if affiliate_id not in affiliate_changes:
                affiliate_changes[affiliate_id] = {
                    'affiliate': commission.affiliate,
                    'commissions': [],
                    'total_amount': Decimal('0')
                }
            
            affiliate_changes[affiliate_id]['commissions'].append(commission)
            affiliate_changes[affiliate_id]['total_amount'] += commission.commission_amount
        
        # Display proposed changes
        self.stdout.write('='*80)
        self.stdout.write('PROPOSED CHANGES:')
        self.stdout.write('='*80 + '\n')
        
        for affiliate_id, data in affiliate_changes.items():
            affiliate = data['affiliate']
            count = len(data['commissions'])
            total = data['total_amount']
            
            new_pending = affiliate.pending_balance - total
            new_available = affiliate.available_balance + total
            
            # Ensure no negative balances
            if new_pending < 0:
                new_pending = Decimal('0')
            
            self.stdout.write(
                f"Affiliate: {affiliate.referral_code:20} (@{affiliate.user.username})"
            )
            self.stdout.write(
                f"  Commissions to update: {count:3} | Total: ₦{total:,.2f}"
            )
            self.stdout.write(
                f"  Current Pending:       ₦{affiliate.pending_balance:>12,.2f}"
            )
            self.stdout.write(
                f"  Current Available:     ₦{affiliate.available_balance:>12,.2f}"
            )
            self.stdout.write(
                self.style.WARNING(f"  → New Pending:         ₦{new_pending:>12,.2f}")
            )
            self.stdout.write(
                self.style.SUCCESS(f"  → New Available:       ₦{new_available:>12,.2f}")
            )
            self.stdout.write('')
        
        # Summary
        total_affected_affiliates = len(affiliate_changes)
        total_amount = sum(data['total_amount'] for data in affiliate_changes.values())
        
        self.stdout.write('='*80)
        self.stdout.write('SUMMARY:')
        self.stdout.write('='*80)
        self.stdout.write(f"Affiliates affected:   {total_affected_affiliates}")
        self.stdout.write(f"Total commissions:     {total_count}")
        self.stdout.write(f"Total amount to move:  ₦{total_amount:,.2f}")
        self.stdout.write('')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - No changes were made\n'))
            self.stdout.write('Run without --dry-run to apply these changes.')
            return
        
        # Confirm before applying
        self.stdout.write(self.style.WARNING(
            '⚠️  WARNING: This will make the following changes:\n'
            '   1. Change commission status from "pending" → "available"\n'
            '   2. Move amounts from pending_balance → available_balance\n'
            '   3. Set available_at to NOW (making funds withdrawable immediately)\n'
            '   4. Affiliates can withdraw these funds once balance >= ₦5,000\n'
        ))
        
        confirm = input('\nType "yes" to continue: ')
        if confirm.lower() != 'yes':
            self.stdout.write(self.style.ERROR('\n✗ Operation cancelled\n'))
            return
        
        # Apply changes
        self.stdout.write('\n' + '='*80)
        self.stdout.write('APPLYING CHANGES...')
        self.stdout.write('='*80 + '\n')
        
        success_count = 0
        error_count = 0
        total_moved = Decimal('0')
        
        for affiliate_id, data in affiliate_changes.items():
            try:
                with transaction.atomic():
                    # Lock the affiliate record
                    affiliate = AffiliateProfile.objects.select_for_update().get(
                        id=affiliate_id
                    )
                    
                    amount_to_move = Decimal('0')
                    commission_ids = []
                    
                    # Update all commissions for this affiliate
                    for commission in data['commissions']:
                        commission.status = 'available'
                        commission.available_at = timezone.now()
                        commission.save(update_fields=['status', 'available_at'])
                        
                        amount_to_move += commission.commission_amount
                        commission_ids.append(commission.id)
                    
                    # Update affiliate balances
                    old_pending = affiliate.pending_balance
                    old_available = affiliate.available_balance
                    
                    affiliate.pending_balance -= amount_to_move
                    affiliate.available_balance += amount_to_move
                    
                    # Safety check: Don't allow negative pending balance
                    if affiliate.pending_balance < 0:
                        affiliate.available_balance += affiliate.pending_balance
                        affiliate.pending_balance = Decimal('0')
                    
                    affiliate.save(update_fields=['pending_balance', 'available_balance'])
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {affiliate.referral_code:20} | "
                            f"Commissions: {len(commission_ids):3} | "
                            f"Moved: ₦{amount_to_move:>10,.2f} | "
                            f"New Available: ₦{affiliate.available_balance:>10,.2f}"
                        )
                    )
                    
                    success_count += 1
                    total_moved += amount_to_move
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Error processing affiliate {data['affiliate'].referral_code}: {str(e)}"
                    )
                )
                error_count += 1
        
        # Final summary
        self.stdout.write('\n' + '='*80)
        self.stdout.write('FINAL SUMMARY:')
        self.stdout.write('='*80)
        self.stdout.write(
            self.style.SUCCESS(f"✓ Successfully fixed:  {success_count} affiliates")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✓ Total amount moved:  ₦{total_moved:,.2f}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"✓ Commissions updated: {total_count}")
        )
        
        if error_count:
            self.stdout.write(
                self.style.ERROR(f"✗ Errors encountered:  {error_count}")
            )
        
        # Check remaining pending commissions
        remaining_pending = AffiliateCommission.objects.filter(status='pending').count()
        
        if remaining_pending == 0:
            self.stdout.write(
                self.style.SUCCESS('\n✓ All commissions are now available!\n')
            )
        else:
            self.stdout.write(
                self.style.WARNING(f'\n⚠️  {remaining_pending} pending commissions remain\n')
            )
        
        self.stdout.write(
            self.style.SUCCESS('✓ Commission status fix complete!\n')
        )
        
        # Post-fix verification
        self.stdout.write('='*80)
        self.stdout.write('VERIFICATION:')
        self.stdout.write('='*80)
        
        status_counts = AffiliateCommission.objects.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        for status_data in status_counts:
            status = status_data['status']
            count = status_data['count']
            self.stdout.write(f"  {status:10}: {count:5} commissions")
        
        self.stdout.write('')