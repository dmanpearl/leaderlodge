"""Load participants from the most recent game for a group and game type."""

from leaderlodge.games.models import Game
from leaderlodge.groups.models import Group


def previous_game_participant_rows(
    group: Group, game_type_code: str
) -> list[dict]:
    """Players from the latest game for this exact group and game type."""
    game = (
        Game.objects.filter(group=group, game_type_code=game_type_code)
        .order_by("-played_on", "-pk")
        .first()
    )
    if game is None:
        return []

    rows = []
    for result in (
        game.participant_results.select_related("player", "player__linked_user")
        .order_by("placement", "pk")
    ):
        player = result.player
        if not player.is_active:
            continue
        rows.append(
            {
                "player": player,
                "player_id": player.pk,
                "guest_name": "",
                "display_label": player.display_label,
                "played": True,
                "score": "",
            }
        )
    return rows


def reuse_players_summary(group: Group, game_type_code: str) -> dict:
    rows = previous_game_participant_rows(group, game_type_code)
    if not rows:
        return {"available": False, "summary": "", "labels": []}
    labels = [row["display_label"] for row in rows]
    return {
        "available": True,
        "summary": ", ".join(labels),
        "labels": labels,
    }
