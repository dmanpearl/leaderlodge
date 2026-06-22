from django.db import migrations, models


def mark_demo_group(apps, schema_editor):
    Group = apps.get_model("groups", "Group")
    Group.objects.filter(name="Demo").update(is_demo=True)


class Migration(migrations.Migration):
    dependencies = [
        ("groups", "0003_groupplayer_hide_from_game_list"),
    ]

    operations = [
        migrations.AddField(
            model_name="group",
            name="is_demo",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled, anyone can view this group read-only "
                    "(demo/sample data)."
                ),
            ),
        ),
        migrations.RunPython(mark_demo_group, migrations.RunPython.noop),
    ]
