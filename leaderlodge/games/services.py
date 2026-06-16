from dataclasses import dataclass
from datetime import date

from django.contrib.auth.models import AbstractBaseUser
from django.core.exceptions import ValidationError
from django.db import transaction

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import get_game_type
from leaderlodge.games.scoring import compute_double_weight
from leaderlodge.groups.models import Group, GroupPlayer, Location


@dataclass
class ParticipantInput:
    player: GroupPlayer
    score: int
    result: str
    placement: int


@transaction.atomic
def record_game(
    *,
    user: AbstractBaseUser,
    group: Group,
    game_type_code: str,
    played_on: date,
    participants: list[ParticipantInput],
    location: Location | None = None,
    import_source: str = "",
    import_row_key: str = "",
) -> Game:
    game_type = get_game_type(game_type_code)

    if not participants:
        raise ValidationError("Select at least one player.")

    player_ids = [p.player.pk for p in participants]
    if len(player_ids) != len(set(player_ids)):
        raise ValidationError("Each player can only appear once.")

    for item in participants:
        if item.player.group_id != group.pk:
            raise ValidationError("All players must belong to the selected group.")

    winner_count = sum(
        1 for p in participants if p.result == GameParticipantResult.Result.WIN
    )
    tie_count = sum(
        1 for p in participants if p.result == GameParticipantResult.Result.TIE
    )
    loser_count = sum(
        1 for p in participants if p.result == GameParticipantResult.Result.LOSS
    )
    game_type.validate(
        player_count=len(participants),
        winner_count=winner_count,
        tie_count=tie_count,
        loser_count=loser_count,
    )

    row_dicts = [
        {
            "player": item.player,
            "score": item.score,
            "result": item.result,
        }
        for item in participants
    ]
    double_weight = compute_double_weight(row_dicts, game_type_code)

    if location is not None:
        if not group.location_library_id:
            raise ValidationError("Group has no location library.")
        if location.library_id != group.location_library_id:
            raise ValidationError("Location must belong to this group's place list.")

    game = Game.objects.create(
        group=group,
        game_type_code=game_type_code,
        played_on=played_on,
        recorded_by=user,
        player_count=len(participants),
        double_weight=double_weight,
        location=location,
        import_source=import_source,
        import_row_key=import_row_key,
    )

    for item in participants:
        GameParticipantResult.objects.create(
            game=game,
            player=item.player,
            score=item.score,
            result=item.result,
            placement=item.placement,
        )

    game.full_clean()
    return game
