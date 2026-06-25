import secrets

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ("groups", "0005_alter_groupplayer_hide_from_game_list"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="GroupInvite",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("email", "Email"), ("share", "Share link")],
                        max_length=10,
                    ),
                ),
                ("email", models.EmailField(blank=True, max_length=254)),
                ("token", models.CharField(max_length=64, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "accepted_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="accepted_group_invites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "group",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="groups.group",
                    ),
                ),
                (
                    "guest_player",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="invites",
                        to="groups.groupplayer",
                    ),
                ),
                (
                    "invited_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="sent_group_invites",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    models.Index(fields=["token"], name="groups_grou_token_0a1b2c_idx"),
                    models.Index(
                        fields=["group", "kind"],
                        name="groups_grou_group_i_3d4e5f_idx",
                    ),
                ],
            },
        ),
    ]
