from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("games", "0004_location_libraries"),
    ]

    operations = [
        migrations.AddField(
            model_name="game",
            name="half_weight",
            field=models.PositiveSmallIntegerField(default=1),
        ),
    ]
