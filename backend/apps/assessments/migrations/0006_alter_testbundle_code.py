from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assessments", "0005_alter_answerresponse_unique_together_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="testbundle",
            name="code",
            field=models.SlugField(
                allow_unicode=True,
                blank=True,
                max_length=64,
                unique=True,
                verbose_name="Код",
            ),
        ),
    ]
