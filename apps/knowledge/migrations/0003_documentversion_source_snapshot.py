from django.db import migrations, models


def snapshot_existing_versions(apps, schema_editor):
    DocumentVersion = apps.get_model("knowledge", "DocumentVersion")
    for version in DocumentVersion.objects.select_related("document").all():
        version.source_file = version.document.source_file.name
        version.file_type = version.document.file_type
        version.sha256 = version.document.sha256
        version.save(update_fields=["source_file", "file_type", "sha256"])


class Migration(migrations.Migration):
    dependencies = [("knowledge", "0002_knowledgebase_access_scope")]

    operations = [
        migrations.AddField(
            model_name="documentversion",
            name="file_type",
            field=models.CharField(blank=True, max_length=16),
        ),
        migrations.AddField(
            model_name="documentversion",
            name="sha256",
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name="documentversion",
            name="source_file",
            field=models.FileField(blank=True, upload_to="documents/%Y/%m/%d"),
        ),
        migrations.RunPython(snapshot_existing_versions, migrations.RunPython.noop),
    ]
