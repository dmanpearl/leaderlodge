"""Last location a user recorded for a game type."""

from django.contrib.auth.models import AbstractBaseUser

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES


def last_recorded_location_name(
    user: AbstractBaseUser | None, game_type_code: str
) -> str:
    if user is None or not user.is_authenticated:
        return ""
    if game_type_code not in GAME_TYPES:
        return ""

    game = (
        Game.objects.filter(
            recorded_by=user,
            game_type_code=game_type_code,
            location__isnull=False,
        )
        .select_related("location")
        .order_by("-played_on", "-created_at", "-pk")
        .first()
    )
    if game is None or game.location is None:
        return ""
    return game.location.name
