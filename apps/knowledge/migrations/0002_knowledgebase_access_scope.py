from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("knowledge", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="knowledgebase",
            name="access_scope",
            field=models.CharField(
                choices=[("organization", "组织内可见"), ("restricted", "仅获授权成员")],
                default="organization",
                max_length=16,
            ),
        ),
    ]
