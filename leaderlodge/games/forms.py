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
        if user is not None:
            from leaderlodge.groups.services import user_groups

            self.fields["group"].queryset = user_groups(user).order_by("name")


def parse_participants_from_post(post, *, group) -> list[dict]:
    rows = []
    player_ids = post.getlist("participant_player_id")
    guest_names = post.getlist("participant_guest_name")
    scores = post.getlist("participant_score")
    for player_id_raw, guest_name, score_raw in zip(
        player_ids, guest_names, scores, strict=False
    ):
        player = resolve_participant_player(
            group=group,
            player_id=player_id_raw.strip() or None,
            guest_name=guest_name.strip() or None,
        )
        if player is None:
            continue
        try:
            score = int(score_raw)
        except (TypeError, ValueError):
            score = 0
        rows.append(
            {
                "player": player,
                "score": score,
                "result": GameParticipantResult.Result.PLAYED,
            }
        )
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
