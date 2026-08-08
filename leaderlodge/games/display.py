from __future__ import annotations

from collections import defaultdict

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.groups.models import GroupPlayer
from leaderlodge.groups.names import disambiguate_labels


def winner_labels_for_games(games: list[Game]) -> dict[int, str]:
    if not games:
        return {}

    game_ids = [game.pk for game in games]
    winners_by_game: dict[int, list[int]] = defaultdict(list)
    ties_by_game: dict[int, list[int]] = defaultdict(list)
    players_by_pk: dict[int, GroupPlayer] = {}

    results = (
        GameParticipantResult.objects.filter(
            game_id__in=game_ids,
            result__in=(
                GameParticipantResult.Result.WIN,
                GameParticipantResult.Result.TIE,
            ),
        )
        .select_related("player", "player__linked_user")
        .order_by("game_id", "placement", "pk")
    )
    for result in results:
        players_by_pk[result.player_id] = result.player
        if result.result == GameParticipantResult.Result.WIN:
            winners_by_game[result.game_id].append(result.player_id)
        else:
            ties_by_game[result.game_id].append(result.player_id)

    label_map = _winner_label_map(players_by_pk)

    labels: dict[int, str] = {}
    for game_id in game_ids:
        if winners_by_game[game_id]:
            labels[game_id] = ", ".join(
                label_map[player_id] for player_id in winners_by_game[game_id]
            )
        elif ties_by_game[game_id]:
            names = ", ".join(
                label_map[player_id] for player_id in ties_by_game[game_id]
            )
            labels[game_id] = f"Tie - {names}"
        else:
            labels[game_id] = "—"
    return labels


def _winner_label_map(players_by_pk: dict[int, GroupPlayer]) -> dict[int, str]:
    """Resolve winner/tie labels with group-scoped first-name disambiguation."""
    if not players_by_pk:
        return {}

    group_ids = {player.group_id for player in players_by_pk.values()}
    roster = list(
        GroupPlayer.objects.filter(
            group_id__in=group_ids,
            is_active=True,
            is_team=False,
        ).select_related("linked_user")
    )
    by_pk = {player.pk: player for player in roster}
    for player in players_by_pk.values():
        by_pk.setdefault(player.pk, player)

    label_map = disambiguate_labels(list(by_pk.values()))
    return {
        player_id: label_map.get(player_id, player.display_label)
        for player_id, player in players_by_pk.items()
    }
