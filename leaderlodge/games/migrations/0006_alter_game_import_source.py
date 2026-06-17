from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0005_game_half_weight"),
    ]

    operations = [
        migrations.AlterField(
            model_name="game",
            name="import_source",
            field=models.CharField(blank=True, max_length=64),
        ),
    ]
