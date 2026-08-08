from __future__ import annotations

from dataclasses import dataclass

from leaderlodge.games.game_type_icons import score_type_icon_url
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import (
    game_type_supports_shutout,
    score_type_icon_filename,
    score_type_label,
)
from leaderlodge.games.shutouts import is_double_skunk_game, is_shutout_game

WEIGHT_GAME_TYPES = frozenset({"dominos", "progressiverummy", "pickleball"})


def show_weight_column(*, games: list[Game], game_type_code: str) -> bool:
    if game_type_code in WEIGHT_GAME_TYPES:
        return True
    # Shutout icons (Pickled / Skunked) render in this column.
    if game_type_supports_shutout(game_type_code):
        return True
    # Mah Jongg style icons (and any future style icons) use this column.
    if score_type_icon_filename(game_type_code, ""):
        return True
    return any(game.double_weight == 2 or game.half_weight == 2 for game in games)


@dataclass(frozen=True)
class GameListScoreCell:
    score: int | None
    css_class: str


@dataclass(frozen=True)
class GameListRow:
    game: Game
    cells: list[GameListScoreCell]
    is_shutout: bool = False
    is_double_skunk: bool = False
    score_type_icon_url: str = ""
    score_type_label: str = ""


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
        participant_rows = list(game_results.values())
        shutout = is_shutout_game(game.game_type_code, participant_rows)
        double_skunk = is_double_skunk_game(game.game_type_code, participant_rows)
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
        style_icon = score_type_icon_url(game.game_type_code, game.score_type)
        style_label = (
            score_type_label(game.game_type_code, game.score_type) if style_icon else ""
        )
        rows.append(
            GameListRow(
                game=game,
                cells=cells,
                is_shutout=shutout,
                is_double_skunk=double_skunk,
                score_type_icon_url=style_icon,
                score_type_label=style_label,
            )
        )

    return player_columns, rows
