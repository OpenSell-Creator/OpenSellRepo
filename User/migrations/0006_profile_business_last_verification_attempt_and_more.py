# Generated by Django 5.1.7 on 2025-07-05 22:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('User', '0005_profile_business_address_visible_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='business_last_verification_attempt',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='business_rejection_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='business_verification_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='profile',
            name='featured_store',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='profile',
            name='permanent_listing_enabled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='profile',
            name='priority_support',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='profile',
            name='business_address_visible',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='business_description',
            field=models.TextField(blank=True, max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='business_type',
            field=models.CharField(blank=True, choices=[('sole_proprietorship', 'Sole Proprietorship'), ('partnership', 'Partnership'), ('limited_liability', 'Limited Liability Company'), ('corporation', 'Corporation'), ('cooperative', 'Cooperative Society'), ('ngo', 'Non-Governmental Organization'), ('other', 'Other')], max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name='profile',
            name='business_verification_status',
            field=models.CharField(choices=[('unverified', 'Unverified'), ('pending', 'Pending Review'), ('verified', 'Verified'), ('rejected', 'Rejected'), ('suspended', 'Suspended')], default='unverified', max_length=20),
        ),
    ]
