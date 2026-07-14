"""Load participants from a prior game for reuse on Record Game."""

from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.groups.models import Group

REUSE_PLAYERS_MAX_GAMES = 6
# Cap history walk so prefetch+dedupe stays fast even with huge group history.
REUSE_PLAYERS_MAX_SCAN = 40


def most_recent_game(group: Group, game_type_code: str) -> Game | None:
    """Latest game for this exact group and game type, or None."""
    games = recent_games_for_reuse(group, game_type_code, limit=1)
    return games[0] if games else None


def recent_games_for_reuse(
    group: Group,
    game_type_code: str,
    *,
    limit: int = REUSE_PLAYERS_MAX_GAMES,
) -> list[Game]:
    """Most recent games for this group and game type, newest first."""
    if game_type_code not in GAME_TYPES or limit <= 0:
        return []

    return list(
        Game.objects.filter(
            group_id=group.pk,
            game_type_code=game_type_code,
        ).order_by(
            "-played_on", "-created_at", "-pk"
        )[:limit]
    )


def participant_rows_from_game(game: Game) -> list[dict]:
    """Sides from a specific game, ready for the Record Game roster form."""
    from leaderlodge.groups.teams import team_member_players

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


def previous_game_participant_rows(group: Group, game_type_code: str) -> list[dict]:
    """Sides from the latest game for this exact group and game type."""
    game = most_recent_game(group, game_type_code)
    if game is None:
        return []
    return participant_rows_from_game(game)


def reuse_option_from_game(game: Game) -> dict | None:
    rows = participant_rows_from_game(game)
    if not rows:
        return None
    labels = [row["display_label"] for row in rows]
    return {
        "game_id": game.pk,
        "summary": ", ".join(labels),
        "labels": labels,
        "lineup_key": _lineup_key(rows),
    }


def _lineup_key(rows: list[dict]) -> frozenset:
    """Order-independent roster identity, including team pairings."""
    sides: list[frozenset[int]] = []
    for row in rows:
        player_id = row.get("player_id")
        if not player_id:
            continue
        member_ids = {int(player_id)}
        teammate_id = row.get("teammate_player_id")
        if teammate_id:
            member_ids.add(int(teammate_id))
        sides.append(frozenset(member_ids))
    return frozenset(sides)


def reuse_players_summary(
    group: Group,
    game_type_code: str,
    *,
    limit: int = REUSE_PLAYERS_MAX_GAMES,
    scan_limit: int = REUSE_PLAYERS_MAX_SCAN,
) -> dict:
    options = []
    seen_lineups: set[frozenset] = set()
    if game_type_code not in GAME_TYPES or limit <= 0 or scan_limit <= 0:
        return {
            "available": False,
            "summary": "",
            "labels": [],
            "options": [],
        }

    # Slice before prefetch_related so Django does not load the full history.
    games = list(
        Game.objects.filter(
            group_id=group.pk,
            game_type_code=game_type_code,
        )
        .order_by("-played_on", "-created_at", "-pk")[:scan_limit]
        .prefetch_related(
            "participant_results__player__linked_user",
            "participant_results__player__team_members__member__linked_user",
        )
    )
    for game in games:
        if len(options) >= limit:
            break
        option = reuse_option_from_game(game)
        if option is None:
            continue
        lineup_key = option.pop("lineup_key")
        if lineup_key in seen_lineups:
            continue
        seen_lineups.add(lineup_key)
        options.append(option)

    if not options:
        return {
            "available": False,
            "summary": "",
            "labels": [],
            "options": [],
        }
    return {
        "available": True,
        "summary": options[0]["summary"],
        "labels": options[0]["labels"],
        "options": options,
    }
