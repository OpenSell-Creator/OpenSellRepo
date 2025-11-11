from django.core.management.base import BaseCommand
from django.db import transaction
from Dashboard.models import AffiliateProfile, Referral

class Command(BaseCommand):
    help = 'Convert existing random referral codes to username-based codes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be changed without making changes',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN MODE - No changes will be made\n'))
        else:
            self.stdout.write(self.style.WARNING(
                '⚠️  This will convert all referral codes to username-based codes.\n'
                'This action cannot be easily reversed.\n'
            ))
            confirm = input('Type "yes" to continue: ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('Operation cancelled'))
                return
        
        affiliates = AffiliateProfile.objects.select_related('user').all()
        
        self.stdout.write(f'\nFound {affiliates.count()} affiliate(s) to process\n')
        
        changes = []
        conflicts = []
        
        for affiliate in affiliates:
            old_code = affiliate.referral_code
            new_code = affiliate.user.username.lower()
            
            # Check for conflicts
            conflict = AffiliateProfile.objects.filter(
                referral_code__iexact=new_code
            ).exclude(id=affiliate.id).first()
            
            if conflict:
                # Add numeric suffix
                counter = 1
                while AffiliateProfile.objects.filter(
                    referral_code__iexact=f"{new_code}{counter}"
                ).exists():
                    counter += 1
                new_code = f"{new_code}{counter}"
                conflicts.append((affiliate, old_code, new_code))
            
            changes.append({
                'affiliate': affiliate,
                'old_code': old_code,
                'new_code': new_code,
                'had_conflict': conflict is not None
            })
        
        # Display proposed changes
        self.stdout.write('\n' + '='*70)
        self.stdout.write('PROPOSED CHANGES:')
        self.stdout.write('='*70 + '\n')
        
        for change in changes:
            status = '⚠️  CONFLICT' if change['had_conflict'] else '✓ OK'
            self.stdout.write(
                f"{status:15} | "
                f"{change['affiliate'].user.username:20} | "
                f"{change['old_code']:15} → {change['new_code']:15}"
            )
        
        if conflicts:
            self.stdout.write(
                f"\n⚠️  {len(conflicts)} conflict(s) found - numeric suffixes will be added"
            )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('\n🔍 DRY RUN - No changes were made')
            )
            return
        
        # Apply changes
        self.stdout.write('\n' + '='*70)
        self.stdout.write('APPLYING CHANGES...')
        self.stdout.write('='*70 + '\n')
        
        success_count = 0
        error_count = 0
        
        for change in changes:
            try:
                with transaction.atomic():
                    affiliate = change['affiliate']
                    old_code = change['old_code']
                    new_code = change['new_code']
                    
                    # Update affiliate profile
                    affiliate.referral_code = new_code
                    affiliate.save(update_fields=['referral_code'])
                    
                    # Update all referrals using this code
                    updated_referrals = Referral.objects.filter(
                        affiliate=affiliate,
                        referral_code_used=old_code
                    ).update(referral_code_used=new_code)
                    
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ {affiliate.user.username}: {old_code} → {new_code} "
                            f"({updated_referrals} referral(s) updated)"
                        )
                    )
                    success_count += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Error processing {affiliate.user.username}: {str(e)}"
                    )
                )
                error_count += 1
        
        # Summary
        self.stdout.write('\n' + '='*70)
        self.stdout.write('SUMMARY:')
        self.stdout.write('='*70)
        self.stdout.write(
            self.style.SUCCESS(f"✓ Successfully converted: {success_count}")
        )
        if error_count:
            self.stdout.write(
                self.style.ERROR(f"✗ Errors: {error_count}")
            )
        if conflicts:
            self.stdout.write(
                self.style.WARNING(f"⚠️  Conflicts resolved: {len(conflicts)}")
            )
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Conversion complete!')
        )