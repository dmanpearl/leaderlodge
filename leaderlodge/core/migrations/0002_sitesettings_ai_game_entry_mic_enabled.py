from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_site_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="sitesettings",
            name="ai_game_entry_mic_enabled",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Show an in-app microphone on Record Game AI entry (browser speech). "
                    "Users can still tap the text field to type or use the system keyboard mic."
                ),
            ),
        ),
    ]
