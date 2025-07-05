from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_alter_chatmessage_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='chatmessage',
            name='read_by',
            field=models.JSONField(default=list),
        ),
    ]
