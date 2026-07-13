from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from leaderlodge.games.location_field import location_name_form_field
from leaderlodge.games.models import Game, GameParticipantResult
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
    location_name = location_name_form_field()

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        from leaderlodge.games.last_location import last_recorded_location_name
        from leaderlodge.groups.services import editable_groups, get_demo_group

        if user is not None and user.is_authenticated:
            qs = editable_groups(user).order_by("name")
            self.fields["group"].queryset = qs
            if qs.count() == 1:
                self.fields["group"].empty_label = None
                if not self.is_bound and not self.initial.get("group"):
                    self.initial["group"] = qs.first()
        else:
            demo = get_demo_group()
            if demo is not None:
                self.fields["group"].queryset = Group.objects.filter(pk=demo.pk)

        if self.is_bound or self.initial.get("location_name"):
            return
        game_type_code = self.initial.get("game_type_code", "")
        if user is not None and game_type_code:
            last_location = last_recorded_location_name(user, game_type_code)
            if last_location:
                self.initial["location_name"] = last_location


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


class GameEditForm(forms.Form):
    played_on = forms.DateField(
        label="Date played",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    location_name = location_name_form_field()
    notes = forms.CharField(
        label="Notes",
        help_text="Required. Explain why this game was edited.",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Why are these changes being made?",
            }
        ),
    )

    def __init__(self, *args, game: Game | None = None, **kwargs):
        self.game = game
        super().__init__(*args, **kwargs)
        if game is None:
            return
        self.fields["played_on"].initial = game.played_on
        if game.location_id:
            self.fields["location_name"].initial = game.location.name
        for participant in game.participant_results.select_related("player").order_by(
            "pk"
        ):
            self.fields[f"score_{participant.pk}"] = forms.IntegerField(
                label=participant.player.display_label,
                initial=participant.score,
                required=False,
                widget=forms.NumberInput(
                    attrs={"class": "form-control game-edit-score-input"}
                ),
            )
            self.fields[f"remove_{participant.pk}"] = forms.CharField(
                required=False,
                widget=forms.HiddenInput(attrs={"class": "game-edit-remove-input"}),
            )

    def clean_notes(self):
        notes = self.cleaned_data["notes"].strip()
        if not notes:
            raise ValidationError(
                "Notes are required explaining why the change was made."
            )
        return notes

    def resolved_location(self):
        if self.game is None:
            return None
        from leaderlodge.groups.locations import resolve_game_location

        return resolve_game_location(
            group=self.game.group,
            location_name=self.cleaned_data.get("location_name", ""),
        )

    def location_changed(self) -> bool:
        if self.game is None:
            return False
        return self.resolved_location() != self.game.location

    def played_on_changed(self) -> bool:
        if self.game is None:
            return False
        return self.cleaned_data["played_on"] != self.game.played_on

    def participant_removals(self) -> set[int]:
        if self.game is None:
            return set()
        removals: set[int] = set()
        for participant in self.game.participant_results.order_by("pk"):
            if self.cleaned_data.get(f"remove_{participant.pk}"):
                removals.add(participant.pk)
        return removals

    def score_updates(self) -> dict[int, int]:
        if self.game is None:
            return {}
        removals = self.participant_removals()
        updates: dict[int, int] = {}
        for participant in self.game.participant_results.order_by("pk"):
            if participant.pk in removals:
                continue
            new_score = self.cleaned_data.get(f"score_{participant.pk}")
            if new_score is not None and new_score != participant.score:
                updates[participant.player_id] = new_score
        return updates

    def clean(self):
        cleaned = super().clean()
        if self.errors:
            return cleaned
        removals = self.participant_removals()
        if removals and self.game is not None:
            remaining = self.game.participant_results.count() - len(removals)
            if not player_count_is_valid(remaining, self.game.game_type_code):
                game_type = get_game_type(self.game.game_type_code)
                raise ValidationError(
                    f"Cannot remove that player - {game_type.name} requires "
                    f"{game_type.min_players} to {game_type.max_players} players."
                )
        if (
            not self.score_updates()
            and not removals
            and not self.location_changed()
            and not self.played_on_changed()
        ):
            raise ValidationError(
                "Change at least one score, the date, or the location before saving."
            )
        return cleaned
