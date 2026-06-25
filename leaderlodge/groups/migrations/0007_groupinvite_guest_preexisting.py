from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0006_groupinvite"),
    ]

    operations = [
        migrations.AddField(
            model_name="groupinvite",
            name="guest_preexisting",
            field=models.BooleanField(
                default=False,
                help_text="True when the invite targets a guest already on the roster.",
            ),
        ),
    ]
