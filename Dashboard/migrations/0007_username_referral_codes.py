"""
Django migration to change referral codes to usernames
Save as: Dashboard/migrations/0XXX_username_referral_codes.py

Run: python manage.py makemigrations --empty Dashboard
Then replace the content with this code
"""

from django.db import migrations
from django.db.models import Q

def migrate_to_username_codes(apps, schema_editor):
    """
    Migrate existing referral codes to usernames
    Handle duplicates by adding numeric suffixes
    """
    AffiliateProfile = apps.get_model('Dashboard', 'AffiliateProfile')
    Referral = apps.get_model('Dashboard', 'Referral')
    
    affiliates = AffiliateProfile.objects.all()
    
    for affiliate in affiliates:
        old_code = affiliate.referral_code
        new_code = affiliate.user.username.lower()
        
        # Check if username is already taken as referral code
        existing = AffiliateProfile.objects.filter(
            referral_code__iexact=new_code
        ).exclude(id=affiliate.id)
        
        if existing.exists():
            # Add numeric suffix if duplicate
            counter = 1
            while AffiliateProfile.objects.filter(
                referral_code__iexact=f"{new_code}{counter}"
            ).exists():
                counter += 1
            new_code = f"{new_code}{counter}"
        
        # Update affiliate profile
        affiliate.referral_code = new_code
        affiliate.save(update_fields=['referral_code'])
        
        # Update all referrals that used this code
        Referral.objects.filter(
            affiliate=affiliate,
            referral_code_used=old_code
        ).update(referral_code_used=new_code)
        
        print(f"Updated {affiliate.user.username}: {old_code} -> {new_code}")

def reverse_migration(apps, schema_editor):
    """
    Reverse is not really possible since we lose the original random codes
    This function just ensures the migration can be reversed without errors
    """
    pass

class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0006_affiliateprofile_affiliatewithdrawal_referral_and_more'),  # Update this
    ]

    operations = [
        migrations.RunPython(
            migrate_to_username_codes,
            reverse_migration
        ),
    ]