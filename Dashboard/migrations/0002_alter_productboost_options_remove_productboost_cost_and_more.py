# Generated by Django 5.1.7 on 2025-06-08 21:06

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Dashboard', '0001_initial'),
        ('Home', '0005_product_listing_boost_score'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='productboost',
            options={'ordering': ['-start_date']},
        ),
        migrations.RemoveField(
            model_name='productboost',
            name='cost',
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='analytics_access',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='boost_discount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=5),
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='featured_listings',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='monthly_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='priority_support',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='tier_type',
            field=models.CharField(choices=[('free', 'Free User'), ('pro', 'Pro User')], default='free', max_length=15),
        ),
        migrations.AddField(
            model_name='accountstatus',
            name='yearly_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=10),
        ),
        migrations.AddField(
            model_name='productboost',
            name='discount_applied',
            field=models.DecimalField(decimal_places=2, default=0, help_text='Discount percentage applied', max_digits=5),
        ),
        migrations.AddField(
            model_name='productboost',
            name='duration_days',
            field=models.PositiveIntegerField(choices=[(1, '1 Day'), (3, '3 Days'), (7, '1 Week'), (14, '2 Weeks'), (30, '1 Month')], default=1),
        ),
        migrations.AddField(
            model_name='productboost',
            name='final_cost',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Actual amount charged', max_digits=10),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='productboost',
            name='original_cost',
            field=models.DecimalField(decimal_places=2, default=0.0, help_text='Cost before any discounts', max_digits=10),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='productboost',
            name='tier_at_purchase',
            field=models.CharField(blank=True, help_text="User's tier when boost was purchased", max_length=50),
        ),
        migrations.AddField(
            model_name='productboost',
            name='user_account',
            field=models.ForeignKey(default=0.0, on_delete=django.db.models.deletion.CASCADE, related_name='product_boosts', to='Dashboard.useraccount'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='productboost',
            name='boost_type',
            field=models.CharField(choices=[('featured', 'Featured Product'), ('urgent', 'Urgent Sale'), ('spotlight', 'Category Spotlight'), ('premium', 'Premium Placement')], max_length=20),
        ),
        migrations.AlterField(
            model_name='transaction',
            name='transaction_type',
            field=models.CharField(choices=[('deposit', 'Deposit'), ('withdrawal', 'Withdrawal'), ('listing_fee', 'Listing Fee'), ('boost_fee', 'Boost Fee'), ('subscription', 'Subscription'), ('refund', 'Refund'), ('bonus', 'Bonus')], max_length=20),
        ),
        migrations.AddIndex(
            model_name='productboost',
            index=models.Index(fields=['product', 'boost_type', 'is_active'], name='Dashboard_p_product_97b02e_idx'),
        ),
        migrations.AddIndex(
            model_name='productboost',
            index=models.Index(fields=['user_account', '-start_date'], name='Dashboard_p_user_ac_ede937_idx'),
        ),
        migrations.AddIndex(
            model_name='productboost',
            index=models.Index(fields=['end_date', 'is_active'], name='Dashboard_p_end_dat_88f2bf_idx'),
        ),
        migrations.AddIndex(
            model_name='transaction',
            index=models.Index(fields=['account', 'transaction_type', '-created_at'], name='Dashboard_t_account_c371b0_idx'),
        ),
    ]
