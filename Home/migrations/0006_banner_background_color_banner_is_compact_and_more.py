# Generated by Django 5.1.7 on 2025-06-27 00:14

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Home', '0005_product_listing_boost_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='banner',
            name='background_color',
            field=models.CharField(blank=True, help_text='Hex color code for banner background (e.g., #FF5733)', max_length=7, null=True),
        ),
        migrations.AddField(
            model_name='banner',
            name='is_compact',
            field=models.BooleanField(default=True, help_text='Use compact design for section banners'),
        ),
        migrations.AlterField(
            model_name='banner',
            name='banner_type',
            field=models.CharField(choices=[('promotional', 'Promotional Banner'), ('section', 'Section Banner')], default='promotional', max_length=20),
        ),
        migrations.AlterField(
            model_name='banner',
            name='display_location',
            field=models.CharField(choices=[('home_section_1', 'Between Featured & Local Products'), ('home_section_2', 'Between Local & Trending Products'), ('home_section_3', 'Between Trending & Categories'), ('category', 'Category Pages'), ('global', 'Global')], default='global', max_length=20),
        ),
    ]
