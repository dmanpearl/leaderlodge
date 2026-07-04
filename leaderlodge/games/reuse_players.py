"""Load participants from the most recent game for a group and game type."""

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.models import Group


def most_recent_game(group: Group, game_type_code: str) -> Game | None:
    """Latest game for this exact group and game type, or None."""
    if game_type_code not in GAME_TYPES:
        return None

    return (
        Game.objects.filter(
            group_id=group.pk,
            game_type_code=game_type_code,
        )
        .order_by("-played_on", "-created_at", "-pk")
        .first()
    )


def previous_game_participant_rows(group: Group, game_type_code: str) -> list[dict]:
    """Sides from the latest game for this exact group and game type."""
    from leaderlodge.groups.teams import team_member_players

    game = most_recent_game(group, game_type_code)
    if game is None:
        return []

    rows = []
    for result in (
        game.participant_results.select_related("player", "player__linked_user")
        .prefetch_related("player__team_members__member__linked_user")
        .order_by("placement", "pk")
    ):
        player = result.player
        if not player.is_active:
            continue
        if player.is_team:
            members = team_member_players(player)
            if not members:
                continue
            primary = members[0]
            teammate = members[1] if len(members) > 1 else None
            rows.append(
                {
                    "player": primary,
                    "player_id": primary.pk,
                    "guest_name": "",
                    "teammate_player_id": teammate.pk if teammate else "",
                    "teammate_guest_name": "",
                    "teammate_display_label": (
                        teammate.display_label if teammate else ""
                    ),
                    "display_label": player.display_label,
                    "played": True,
                    "score": "",
                }
            )
            continue
        rows.append(
            {
                "player": player,
                "player_id": player.pk,
                "guest_name": "",
                "teammate_player_id": "",
                "teammate_guest_name": "",
                "teammate_display_label": "",
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
