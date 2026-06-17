from typing import Protocol

from django.core.exceptions import ValidationError


class GameTypeValidation(Protocol):
    min_players: int
    max_players: int
    supports_loser: bool


def validate_player_count(
    *,
    player_count: int,
    min_players: int,
    max_players: int,
) -> None:
    if player_count < min_players or player_count > max_players:
        raise ValidationError(
            f"This game requires {min_players} to {max_players} players "
            f"({player_count} provided)."
        )


def validate_game_results(
    *,
    supports_loser: bool,
    player_count: int,
    winner_count: int,
    tie_count: int,
    loser_count: int,
) -> None:
    if winner_count > 1:
        raise ValidationError("At most one winner is allowed.")

    if winner_count == 1 and tie_count > 0:
        raise ValidationError("Cannot have both a winner and a tie at the top.")

    if winner_count == 0 and tie_count == 0:
        raise ValidationError("Must have a winner or a tie at the top.")

    if supports_loser:
        all_tied = tie_count == player_count and winner_count == 0
        if not all_tied and loser_count < 1:
            raise ValidationError("At least one loser is required for this game type.")
    elif loser_count != 0:
        raise ValidationError("This game type does not use a loser.")


def validate_game_for_type(
    *,
    game_type: GameTypeValidation,
    player_count: int,
    winner_count: int,
    tie_count: int,
    loser_count: int,
) -> None:
    validate_player_count(
        player_count=player_count,
        min_players=game_type.min_players,
        max_players=game_type.max_players,
    )
    validate_game_results(
        supports_loser=game_type.supports_loser,
        player_count=player_count,
        winner_count=winner_count,
        tie_count=tie_count,
        loser_count=loser_count,
    )
