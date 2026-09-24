from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0003_documentversion_source_snapshot")]

    operations = [
        migrations.AddField(
            model_name="knowledgebase",
            name="assistant_prompt",
            field=models.TextField(blank=True),
        ),
    ]
