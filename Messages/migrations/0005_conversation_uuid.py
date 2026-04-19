# Messages/migrations/0005_conversation_uuid.py

import uuid
from django.db import migrations, models


def populate_uuids(apps, schema_editor):
    """Assign a unique UUID to every existing conversation row."""
    Conversation = apps.get_model('Messages', 'Conversation')
    for conv in Conversation.objects.all():
        conv.uuid = uuid.uuid4()
        conv.save(update_fields=['uuid'])


class Migration(migrations.Migration):

    dependencies = [
        ('Messages', '0004_add_conversation_to_inquiry'),
    ]

    operations = [
        # Step 1: add the field as nullable (no unique yet — avoids the constraint crash)
        migrations.AddField(
            model_name='conversation',
            name='uuid',
            field=models.UUIDField(null=True, blank=True),
        ),

        # Step 2: populate every existing row with a unique UUID
        migrations.RunPython(populate_uuids, migrations.RunPython.noop),

        # Step 3: now enforce unique + not null
        migrations.AlterField(
            model_name='conversation',
            name='uuid',
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),
    ]