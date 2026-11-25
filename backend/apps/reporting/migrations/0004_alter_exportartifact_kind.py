from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("reporting", "0003_alter_aggregatesnapshot_options_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="exportartifact",
            name="kind",
            field=models.CharField(
                choices=[("pdf", "PDF"), ("xlsx", "XLSX"), ("csv", "CSV")],
                max_length=8,
                verbose_name="Тип",
            ),
        ),
    ]
