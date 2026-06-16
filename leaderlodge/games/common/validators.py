from django.core.exceptions import ValidationError


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


def validate_winner_loser(
    *,
    supports_loser: bool,
    winner_count: int,
    loser_count: int,
) -> None:
    if winner_count != 1:
        raise ValidationError("Exactly one winner is required.")

    if supports_loser:
        if loser_count != 1:
            raise ValidationError("Exactly one loser is required for this game type.")
    elif loser_count != 0:
        raise ValidationError("This game type does not use a loser field.")
