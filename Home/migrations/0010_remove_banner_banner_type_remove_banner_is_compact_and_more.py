# Generated by Django 5.1.7 on 2025-06-28 17:35

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Home', '0009_remove_banner_subtitle_remove_banner_title_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='banner',
            name='banner_type',
        ),
        migrations.RemoveField(
            model_name='banner',
            name='is_compact',
        ),
        migrations.AlterField(
            model_name='banner',
            name='display_location',
            field=models.CharField(choices=[('first', 'Homepage - First Position'), ('second', 'Homepage - Second Position'), ('global', 'Global - Top of Pages')], default='global', max_length=20),
        ),
        migrations.AlterField(
            model_name='banner',
            name='image',
            field=models.ImageField(help_text='Advertisement image with all text and design elements included. Global: 1200x400px (desktop), Section: flexible', upload_to='banners/', validators=[django.core.validators.FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]),
        ),
        migrations.AlterField(
            model_name='banner',
            name='mobile_image',
            field=models.ImageField(blank=True, help_text='Mobile-optimized version. Global: 800x200px, Section: flexible', null=True, upload_to='banners/mobile/', validators=[django.core.validators.FileExtensionValidator(['jpg', 'jpeg', 'png', 'webp'])]),
        ),
    ]
