from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("organizations", "0004_organization_test_bundles"),
    ]

    operations = [
        migrations.AlterField(
            model_name="stream",
            name="code",
            field=models.CharField(blank=True, max_length=64, verbose_name="Код"),
        ),
    ]
