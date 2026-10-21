from django.db import migrations, models

# Положение о пользовательских ролях свело пять ролей к трём (участник + два администратора).
# Участник логина не имеет и в StaffProfile не хранится, поэтому здесь остаётся две роли.
ROLE_MAP = {
    "coordinator": "org_admin",
    "hr": "org_admin",
    "prodex_account": "prodex_admin",
    "methodologist": "prodex_admin",
    "sysadmin": "prodex_admin",
}

# Обратное отображение неизбежно с потерей: из org_admin уже не узнать, был это координатор или HR.
# Берём по одному представителю на группу — этого достаточно, чтобы миграция была обратимой.
REVERSE_ROLE_MAP = {"org_admin": "hr", "prodex_admin": "prodex_account"}


def _remap(apps, mapping):
    StaffProfile = apps.get_model("identity", "StaffProfile")
    for old_role, new_role in mapping.items():
        StaffProfile.objects.filter(role=old_role).update(role=new_role)


def collapse_roles(apps, schema_editor):
    _remap(apps, ROLE_MAP)


def expand_roles(apps, schema_editor):
    _remap(apps, REVERSE_ROLE_MAP)


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0002_alter_auditevent_options_alter_staffprofile_options_and_more"),
    ]

    operations = [
        migrations.RunPython(collapse_roles, expand_roles),
        migrations.AlterField(
            model_name="staffprofile",
            name="role",
            field=models.CharField(
                choices=[("org_admin", "Администратор организации"), ("prodex_admin", "Администратор PRODEX")],
                max_length=32,
                verbose_name="Роль",
            ),
        ),
    ]
