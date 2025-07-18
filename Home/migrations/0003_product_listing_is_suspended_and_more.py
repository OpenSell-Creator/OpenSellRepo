# Generated by Django 5.1.7 on 2025-05-21 02:41

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Home', '0002_alter_product_listing_listing_type'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='product_listing',
            name='is_suspended',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='product_listing',
            name='suspended_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='product_listing',
            name='suspended_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='suspended_listings', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='product_listing',
            name='suspension_reason',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name='ProductReport',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.CharField(choices=[('spam', 'Spam or Misleading Content'), ('fraud', 'Fraudulent Listing'), ('inappropriate', 'Inappropriate Content'), ('expired', 'Expired or Sold Item'), ('other', 'Other Reason')], max_length=20)),
                ('details', models.TextField()),
                ('reporter_email', models.EmailField(blank=True, max_length=254, null=True)),
                ('reported_at', models.DateTimeField(auto_now_add=True)),
                ('status', models.CharField(choices=[('pending', 'Pending Review'), ('reviewing', 'Under Review'), ('resolved', 'Resolved'), ('dismissed', 'Dismissed')], default='pending', max_length=10)),
                ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                ('resolution_notes', models.TextField(blank=True, null=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reports', to='Home.product_listing')),
                ('reviewed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_reports', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['-reported_at'],
            },
        ),
    ]
