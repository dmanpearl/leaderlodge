"""Static paths for per-game-type dashboard and list icons."""

from django.templatetags.static import static

from leaderlodge.games.registry import GAME_TYPES

GAME_TYPE_ICON_IMAGE_PREFIX = "img/game-types/"


def game_type_icon_image(game_type_code: str) -> str:
    game_type = GAME_TYPES.get(game_type_code)
    if game_type is None:
        return ""
    return f"{GAME_TYPE_ICON_IMAGE_PREFIX}{game_type.icon_filename}"


def game_type_icon_url(game_type_code: str) -> str:
    image_path = game_type_icon_image(game_type_code)
    if not image_path:
        return ""
    return static(image_path)


def shutout_icon_url(game_type_code: str) -> str:
    from leaderlodge.games.registry import game_type_shutout_config

    config = game_type_shutout_config(game_type_code)
    if config is None:
        return ""
    return static(f"{GAME_TYPE_ICON_IMAGE_PREFIX}{config.icon_filename}")
