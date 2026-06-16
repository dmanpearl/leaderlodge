from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from leaderlodge.games.models import GameParticipantResult
from leaderlodge.games.registry import game_type_choices, get_game_type
from leaderlodge.games.scoring import assign_results_from_scores, player_count_is_valid
from leaderlodge.groups.models import Group


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

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if user is not None:
            from leaderlodge.groups.services import user_groups

            self.fields["group"].queryset = user_groups(user).order_by("name")


def parse_participants_from_post(post, players) -> list[dict]:
    rows = []
    for player in players:
        if post.get(f"play_{player.pk}") != "on":
            continue
        score_raw = post.get(f"score_{player.pk}", "0")
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
