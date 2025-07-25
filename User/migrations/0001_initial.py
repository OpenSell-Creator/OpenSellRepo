# Generated by Django 5.0.1 on 2025-03-21 10:29

import User.utils
import django.db.models.deletion
import imagekit.models.fields
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LGA',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='State',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Location',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('address', models.CharField(blank=True, max_length=120, null=True)),
                ('address_2', models.CharField(blank=True, max_length=120, null=True)),
                ('city', models.CharField(blank=True, max_length=100, null=True)),
                ('lga', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='User.lga')),
                ('state', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='User.state')),
            ],
        ),
        migrations.CreateModel(
            name='Profile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('photo', imagekit.models.fields.ProcessedImageField(null=True, upload_to=User.utils.user_directory_path)),
                ('bio', models.CharField(blank=True, max_length=225)),
                ('phone_number', models.CharField(blank=True, max_length=11)),
                ('location', models.OneToOneField(null=True, on_delete=django.db.models.deletion.SET_NULL, to='User.location')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='lga',
            name='state',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lgas', to='User.state'),
        ),
        migrations.AlterUniqueTogether(
            name='lga',
            unique_together={('name', 'state')},
        ),
    ]
