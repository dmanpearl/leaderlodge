from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Count, Max, Min, Q, QuerySet, Sum

from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import GAME_TYPES, ScoreDirection, get_game_type
from leaderlodge.groups.models import GroupPlayer

STAT_CELL_BEST = "game-list-stats-cell--best"
STAT_CELL_WORST = "game-list-stats-cell--worst"
STAT_CELL_TIE = "game-list-stats-cell--tie"


@dataclass(frozen=True)
class PlayerListStats:
    player: GroupPlayer
    games_played: int
    wins: int
    ties: int
    losses: int
    total_points: int
    max_score: int
    min_score: int


@dataclass(frozen=True)
class GameListStatCell:
    value: int
    css_class: str


@dataclass(frozen=True)
class GameListStatRow:
    label: str
    player_cells: tuple[GameListStatCell, ...]
    global_cell: GameListStatCell | None = None


@dataclass(frozen=True)
class GameListStats:
    total_games: int
    show_losses: bool
    global_max_score: int | None
    global_min_score: int | None
    players: tuple[PlayerListStats, ...]
    rows: tuple[GameListStatRow, ...]


def _player_values(players: tuple[PlayerListStats, ...], field: str) -> list[int]:
    return [getattr(player, field) for player in players]


def _highlight_extremes(
    values: list[int],
    *,
    higher_is_best: bool,
) -> list[str]:
    if len(values) < 2:
        return [""] * len(values)

    best_value = max(values) if higher_is_best else min(values)
    worst_value = min(values) if higher_is_best else max(values)
    if best_value == worst_value:
        return [""] * len(values)

    classes: list[str] = []
    for value in values:
        if value == best_value:
            classes.append(STAT_CELL_BEST)
        elif value == worst_value:
            classes.append(STAT_CELL_WORST)
        else:
            classes.append("")
    return classes


def _highlight_most_ties(values: list[int]) -> list[str]:
    if len(values) < 2:
        return [""] * len(values)

    highest = max(values)
    if highest == 0:
        return [""] * len(values)

    return [STAT_CELL_TIE if value == highest else "" for value in values]


def _make_cells(values: list[int], classes: list[str]) -> tuple[GameListStatCell, ...]:
    return tuple(
        GameListStatCell(value=value, css_class=css_class)
        for value, css_class in zip(values, classes, strict=True)
    )


def _build_stat_rows(
    *,
    players: tuple[PlayerListStats, ...],
    total_games: int,
    show_losses: bool,
    score_direction: ScoreDirection | None,
    global_max_score: int | None,
    global_min_score: int | None,
) -> tuple[GameListStatRow, ...]:
    rows: list[GameListStatRow] = []

    games_values = _player_values(players, "games_played")
    rows.append(
        GameListStatRow(
            label="Total games",
            player_cells=_make_cells(
                games_values,
                _highlight_extremes(games_values, higher_is_best=True),
            ),
            global_cell=GameListStatCell(value=total_games, css_class=""),
        )
    )

    win_values = _player_values(players, "wins")
    rows.append(
        GameListStatRow(
            label="Wins",
            player_cells=_make_cells(
                win_values,
                _highlight_extremes(win_values, higher_is_best=True),
            ),
        )
    )

    tie_values = _player_values(players, "ties")
    rows.append(
        GameListStatRow(
            label="Ties",
            player_cells=_make_cells(tie_values, _highlight_most_ties(tie_values)),
        )
    )

    if show_losses:
        loss_values = _player_values(players, "losses")
        rows.append(
            GameListStatRow(
                label="Losses",
                player_cells=_make_cells(
                    loss_values,
                    _highlight_extremes(loss_values, higher_is_best=False),
                ),
            )
        )

    higher_is_best = score_direction == ScoreDirection.HIGH_WINS
    score_fields = (
        ("Total points", "total_points", None),
        ("High score", "max_score", global_max_score),
        ("Low score", "min_score", global_min_score),
    )
    if score_direction is not None:
        for label, field, global_value in score_fields:
            values = _player_values(players, field)
            global_cell = None
            if global_value is not None:
                global_cell = GameListStatCell(value=global_value, css_class="")
            rows.append(
                GameListStatRow(
                    label=label,
                    player_cells=_make_cells(
                        values,
                        _highlight_extremes(values, higher_is_best=higher_is_best),
                    ),
                    global_cell=global_cell,
                )
            )
    else:
        for label, field, global_value in score_fields:
            values = _player_values(players, field)
            global_cell = None
            if global_value is not None:
                global_cell = GameListStatCell(value=global_value, css_class="")
            rows.append(
                GameListStatRow(
                    label=label,
                    player_cells=tuple(
                        GameListStatCell(value=value, css_class="") for value in values
                    ),
                    global_cell=global_cell,
                )
            )

    return tuple(rows)


def build_game_list_stats(
    *,
    games_qs: QuerySet[Game],
    game_type_code: str,
) -> GameListStats | None:
    """
    Aggregate stats for the full filtered game queryset (not a paginated page).
    """
    if not games_qs.exists():
        return None

    total_games = games_qs.count()
    show_losses = (
        game_type_code in GAME_TYPES
        and get_game_type(game_type_code).supports_loser
    )

    results_qs = GameParticipantResult.objects.filter(game__in=games_qs)
    global_agg = results_qs.aggregate(
        global_max_score=Max("score"),
        global_min_score=Min("score"),
    )

    player_rows = (
        results_qs.values("player_id")
        .annotate(
            games_played=Count("pk"),
            wins=Count("pk", filter=Q(result=GameParticipantResult.Result.WIN)),
            ties=Count("pk", filter=Q(result=GameParticipantResult.Result.TIE)),
            losses=Count("pk", filter=Q(result=GameParticipantResult.Result.LOSS)),
            total_points=Sum("score"),
            max_score=Max("score"),
            min_score=Min("score"),
        )
        .order_by("player_id")
    )

    player_ids = [row["player_id"] for row in player_rows]
    players_by_id = {
        player.pk: player
        for player in GroupPlayer.objects.filter(pk__in=player_ids).select_related(
            "linked_user"
        )
    }

    players: list[PlayerListStats] = []
    for row in player_rows:
        player = players_by_id[row["player_id"]]
        players.append(
            PlayerListStats(
                player=player,
                games_played=row["games_played"] or 0,
                wins=row["wins"] or 0,
                ties=row["ties"] or 0,
                losses=row["losses"] or 0,
                total_points=row["total_points"] or 0,
                max_score=row["max_score"],
                min_score=row["min_score"],
            )
        )

    players.sort(key=lambda item: item.player.display_label.lower())
    players_tuple = tuple(players)
    score_direction = None
    if game_type_code in GAME_TYPES:
        score_direction = get_game_type(game_type_code).score_direction

    return GameListStats(
        total_games=total_games,
        show_losses=show_losses,
        global_max_score=global_agg["global_max_score"],
        global_min_score=global_agg["global_min_score"],
        players=players_tuple,
        rows=_build_stat_rows(
            players=players_tuple,
            total_games=total_games,
            show_losses=show_losses,
            score_direction=score_direction,
            global_max_score=global_agg["global_max_score"],
            global_min_score=global_agg["global_min_score"],
        ),
    )
