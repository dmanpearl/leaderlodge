from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import game_type_choices, get_game_type
from leaderlodge.games.scoring import assign_results_from_scores, player_count_is_valid
from leaderlodge.groups.models import Group
from leaderlodge.groups.player_search import resolve_participant_player


class GameRecordForm(forms.Form):
    group = forms.ModelChoiceField(
        queryset=Group.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    game_type_code = forms.ChoiceField(
        choices=[("", "Choose a game")] + game_type_choices(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    played_on = forms.DateField(
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    location_name = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Optional",
                "autocomplete": "off",
                "data-location-autocomplete": "true",
            }
        ),
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        from leaderlodge.groups.services import editable_groups, get_demo_group

        if user is not None and user.is_authenticated:
            self.fields["group"].queryset = editable_groups(user).order_by("name")
        else:
            demo = get_demo_group()
            if demo is not None:
                self.fields["group"].queryset = Group.objects.filter(pk=demo.pk)


def _resolve_side_members_from_post(
    *,
    group,
    player_id_raw: str,
    guest_name: str,
    teammate_player_id_raw: str,
    teammate_guest_name: str,
) -> list:
    from leaderlodge.groups.teams import resolve_side_player, validate_side_members

    members = []
    primary = resolve_participant_player(
        group=group,
        player_id=player_id_raw.strip() or None,
        guest_name=guest_name.strip() or None,
    )
    if primary is None:
        return []
    members.append(primary)

    teammate = resolve_participant_player(
        group=group,
        player_id=teammate_player_id_raw.strip() or None,
        guest_name=teammate_guest_name.strip() or None,
    )
    if teammate is not None:
        members.append(teammate)

    validate_side_members(members, group=group)
    return members


def parse_participants_from_post(post, *, group) -> list[dict]:
    from leaderlodge.groups.teams import (
        resolve_side_player,
        validate_sides_no_shared_players,
    )

    rows = []
    player_ids = post.getlist("participant_player_id")
    guest_names = post.getlist("participant_guest_name")
    teammate_player_ids = post.getlist("participant_teammate_player_id")
    teammate_guest_names = post.getlist("participant_teammate_guest_name")
    scores = post.getlist("participant_score")

    # Older forms omit teammate fields; pad to match side count.
    while len(teammate_player_ids) < len(player_ids):
        teammate_player_ids.append("")
    while len(teammate_guest_names) < len(player_ids):
        teammate_guest_names.append("")

    sides: list[list] = []
    for (
        player_id_raw,
        guest_name,
        teammate_player_id_raw,
        teammate_guest_name,
        score_raw,
    ) in zip(
        player_ids,
        guest_names,
        teammate_player_ids,
        teammate_guest_names,
        scores,
        strict=False,
    ):
        members = _resolve_side_members_from_post(
            group=group,
            player_id_raw=player_id_raw,
            guest_name=guest_name,
            teammate_player_id_raw=teammate_player_id_raw,
            teammate_guest_name=teammate_guest_name,
        )
        if not members:
            continue
        sides.append(members)
        try:
            score = int(score_raw)
        except (TypeError, ValueError):
            score = 0
        side_player = resolve_side_player(group=group, members=members)
        rows.append(
            {
                "player": side_player,
                "score": score,
                "result": GameParticipantResult.Result.PLAYED,
                "members": members,
            }
        )

    validate_sides_no_shared_players(sides)
    return rows


def prepare_participant_rows(rows: list[dict], game_type_code: str) -> list[dict]:
    if not rows:
        raise ValidationError("Select at least one player who took part.")
    if not player_count_is_valid(len(rows), game_type_code):
        game_type = get_game_type(game_type_code)
        raise ValidationError(
            f"This game requires {game_type.min_players} to "
            f"{game_type.max_players} players."
        )
    assign_results_from_scores(rows, game_type_code)
    return rows
