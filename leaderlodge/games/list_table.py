from __future__ import annotations

from dataclasses import dataclass

from leaderlodge.games.models import Game, GameParticipantResult


@dataclass(frozen=True)
class GameListScoreCell:
    score: int | None
    css_class: str


@dataclass(frozen=True)
class GameListRow:
    game: Game
    cells: list[GameListScoreCell]


def result_cell_class(*, result: str, is_double: bool) -> str:
    if result == GameParticipantResult.Result.WIN:
        return "game-list-cell--win-double" if is_double else "game-list-cell--win"
    if result == GameParticipantResult.Result.LOSS:
        return "game-list-cell--loss-double" if is_double else "game-list-cell--loss"
    if result == GameParticipantResult.Result.TIE:
        return "game-list-cell--tie"
    return ""


def build_game_list_table(games: list[Game]) -> tuple[list, list[GameListRow]]:
    if not games:
        return [], []

    game_ids = [game.pk for game in games]
    participant_results = (
        GameParticipantResult.objects.filter(game_id__in=game_ids)
        .select_related("player", "player__linked_user")
        .order_by("game_id", "placement", "pk")
    )

    players_by_id: dict[int, object] = {}
    results_by_game: dict[int, dict[int, GameParticipantResult]] = {}
    for participant in participant_results:
        players_by_id[participant.player_id] = participant.player
        results_by_game.setdefault(participant.game_id, {})[
            participant.player_id
        ] = participant

    player_columns = sorted(
        players_by_id.values(),
        key=lambda player: player.display_label.lower(),
    )

    rows: list[GameListRow] = []
    for game in games:
        game_results = results_by_game.get(game.pk, {})
        is_double = game.double_weight == 2
        cells = []
        for player in player_columns:
            participant = game_results.get(player.pk)
            if participant is None:
                cells.append(GameListScoreCell(score=None, css_class=""))
            else:
                cells.append(
                    GameListScoreCell(
                        score=participant.score,
                        css_class=result_cell_class(
                            result=participant.result,
                            is_double=is_double,
                        ),
                    )
                )
        rows.append(GameListRow(game=game, cells=cells))

    return player_columns, rows
