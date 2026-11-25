from django.db import migrations, models


def mark_existing_demo_organizations(apps, schema_editor):
    organizations = apps.get_model("organizations", "Organization").objects.using(schema_editor.connection.alias)
    for code, name in (
        ("demo-entry-code", "Демо-организация PRODEX"),
        ("iipb-test-only", "Тестирование ИИПБ"),
    ):
        organizations.filter(entry_code=code, name=name).update(is_demo=True)


class Migration(migrations.Migration):
    dependencies = [("organizations", "0006_organization_physician_contact_and_more")]
    operations = [
        migrations.AddField(
            model_name="organization",
            name="is_demo",
            field=models.BooleanField(default=False, verbose_name="Демоорганизация"),
        ),
        migrations.RunPython(mark_existing_demo_organizations, migrations.RunPython.noop),
    ]
