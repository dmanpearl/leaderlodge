from __future__ import annotations

from collections import defaultdict

from leaderlodge.games.models import Game, GameParticipantResult


def winner_labels_for_games(games: list[Game]) -> dict[int, str]:
    if not games:
        return {}

    game_ids = [game.pk for game in games]
    winners_by_game: dict[int, list[str]] = defaultdict(list)
    ties_by_game: dict[int, list[str]] = defaultdict(list)

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
        label = result.player.display_label
        if result.result == GameParticipantResult.Result.WIN:
            winners_by_game[result.game_id].append(label)
        else:
            ties_by_game[result.game_id].append(label)

    labels: dict[int, str] = {}
    for game_id in game_ids:
        if winners_by_game[game_id]:
            labels[game_id] = ", ".join(winners_by_game[game_id])
        elif ties_by_game[game_id]:
            names = ", ".join(ties_by_game[game_id])
            labels[game_id] = f"Tie — {names}"
        else:
            labels[game_id] = "—"
    return labels
