from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from django.db.models import Count, Q

from leaderlodge.games.list_stats import build_game_list_stats
from leaderlodge.games.models import Game, GameParticipantResult
from leaderlodge.games.registry import ScoreDirection, get_game_type
from leaderlodge.groups.models import GroupPlayer
from leaderlodge.leaderboards.ranking import compute_percentage
from leaderlodge.leaderboards.service import (
    filter_results_through_game,
    get_ranked_standings_at_game,
    get_standings_at_game,
)

ChangeDirection = Literal["up", "down", "same", "none"]
StandingHighlight = Literal["", "overtook", "overtaken"]


@dataclass(frozen=True)
class MatchupCell:
    display: str
    change: ChangeDirection = "none"
    css_class: str = ""
    standing_highlight: StandingHighlight = ""


@dataclass(frozen=True)
class MatchupStatRow:
    label: str
    cells: tuple[MatchupCell, ...]


@dataclass(frozen=True)
class MatchupPlayerColumn:
    player: GroupPlayer
    standing_highlight: StandingHighlight = ""


@dataclass(frozen=True)
class MatchupView:
    game: Game
    game_type_name: str
    low_wins: bool
    show_losses: bool
    players: tuple[MatchupPlayerColumn, ...]
    rows: tuple[MatchupStatRow, ...]


def build_matchup_view(game: Game) -> MatchupView:
    game_type = get_game_type(game.game_type_code)
    low_wins = game_type.score_direction == ScoreDirection.LOW_WINS
    results = list(
        game.participant_results.select_related("player__linked_user").order_by(
            "placement", "pk"
        )
    )
    players = [result.player for result in results]

    before_ranked = _rankings_by_player(
        get_ranked_standings_at_game(
            game.group,
            game.game_type_code,
            game,
            include_game=False,
        )
    )
    after_ranked = _rankings_by_player(
        get_ranked_standings_at_game(
            game.group,
            game.game_type_code,
            game,
            include_game=True,
        )
    )
    before_standings = _standings_by_player(
        get_standings_at_game(
            game.group,
            game.game_type_code,
            game,
            include_game=False,
        )
    )
    after_standings = _standings_by_player(
        get_standings_at_game(
            game.group,
            game.game_type_code,
            game,
            include_game=True,
        )
    )

    standing_highlights = _standing_highlights(
        [player.pk for player in players],
        before_ranked,
        after_ranked,
    )
    player_columns = tuple(
        MatchupPlayerColumn(
            player=player,
            standing_highlight=standing_highlights.get(player.pk, ""),
        )
        for player in players
    )

    h2h_before = _head_to_head_stats(game, players, include_game=False)
    h2h_after = _head_to_head_stats(game, players, include_game=True)
    placements_this_game = {result.player.pk: result.placement for result in results}
    after_place_pct = _place_pct_by_player(
        game,
        placements_this_game,
        [player.pk for player in players],
        include_game=True,
    )

    rows: list[MatchupStatRow] = []
    rows.append(_this_game_score_row(results, low_wins=low_wins))
    rows.append(_this_game_place_row(results))
    rows.append(_place_pct_row(players, after_place_pct))
    rows.append(_this_game_result_row(results))
    rows.extend(
        _leaderboard_rows(
            players,
            before_ranked,
            after_ranked,
            before_standings,
            after_standings,
            standing_highlights,
            show_losses=game_type.supports_loser,
        )
    )
    rows.extend(
        _head_to_head_rows(
            players, h2h_before, h2h_after, show_losses=game_type.supports_loser
        )
    )

    return MatchupView(
        game=game,
        game_type_name=game_type.name,
        low_wins=low_wins,
        show_losses=game_type.supports_loser,
        players=player_columns,
        rows=tuple(rows),
    )


def _rankings_by_player(rows):
    return {row.player.pk: row for row in rows}


def _standings_by_player(rows):
    return {row.player.pk: row for row in rows}


def _rank_sort_key(rank: int | None) -> float:
    return float(rank) if rank is not None else float("inf")


def _standing_highlights(
    player_ids: list[int],
    before_ranked,
    after_ranked,
) -> dict[int, StandingHighlight]:
    highlights: dict[int, StandingHighlight] = {
        player_id: "" for player_id in player_ids
    }

    for player_id in player_ids:
        before_rank = before_ranked.get(player_id)
        after_rank = after_ranked.get(player_id)
        before_value = _rank_sort_key(before_rank.rank if before_rank else None)
        after_value = _rank_sort_key(after_rank.rank if after_rank else None)

        for other_id in player_ids:
            if other_id == player_id:
                continue
            other_before = before_ranked.get(other_id)
            other_after = after_ranked.get(other_id)
            other_before_value = _rank_sort_key(
                other_before.rank if other_before else None
            )
            other_after_value = _rank_sort_key(
                other_after.rank if other_after else None
            )

            was_behind = before_value > other_before_value
            now_ahead = after_value < other_after_value
            was_ahead = before_value < other_before_value
            now_behind = after_value > other_after_value

            if was_behind and now_ahead:
                highlights[player_id] = "overtook"
            if was_ahead and now_behind:
                highlights[player_id] = "overtaken"

    return highlights


def _change_direction(
    before: float | int | None,
    after: float | int | None,
    *,
    higher_is_better: bool,
) -> ChangeDirection:
    if before is None and after is None:
        return "same"
    if before is None or after is None:
        return "none"
    if before == after:
        return "same"
    improved = after > before if higher_is_better else after < before
    return "up" if improved else "down"


def _format_rank(rank: int | None) -> str:
    return str(rank) if rank is not None else "—"


def _format_weighted(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _format_score(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.1f}"


def _format_pct(value: float) -> str:
    return f"{value:.1f}%"


def _display_place(placement: int | None) -> str:
    if placement is None:
        return "—"
    return str(placement + 1)


def _place_pct_by_player(
    game: Game,
    placements_this_game: dict[int, int | None],
    player_ids: list[int],
    *,
    include_game: bool,
) -> dict[int, float | None]:
    """Share of weighted games where the player finished in this game's place."""
    from collections import defaultdict

    results_qs = GameParticipantResult.objects.filter(
        game__group=game.group,
        game__game_type_code=game.game_type_code,
        player_id__in=player_ids,
    ).select_related("game")
    results_qs = filter_results_through_game(
        results_qs, game, include_game=include_game
    )

    totals: dict[int, dict[str, float]] = defaultdict(
        lambda: {"weighted_games": 0.0, "matching": 0.0}
    )
    for result in results_qs:
        target_placement = placements_this_game.get(result.player_id)
        if target_placement is None:
            continue
        weight = result.game.double_weight / result.game.half_weight
        placement = result.placement if result.placement is not None else 0
        bucket = totals[result.player_id]
        bucket["weighted_games"] += weight
        if placement == target_placement:
            bucket["matching"] += weight

    place_pct: dict[int, float | None] = {}
    for player_id in player_ids:
        if placements_this_game.get(player_id) is None:
            place_pct[player_id] = None
            continue
        bucket = totals.get(player_id)
        if not bucket or bucket["weighted_games"] <= 0:
            place_pct[player_id] = None
            continue
        place_pct[player_id] = compute_percentage(
            bucket["matching"], bucket["weighted_games"]
        )
    return place_pct


def _after_value_cell(
    value: float | int | None,
    *,
    formatter,
) -> MatchupCell:
    return MatchupCell(
        display=formatter(value) if value is not None else "—",
    )


def _delta_cell(
    before: float | int | None,
    after: float | int | None,
    *,
    higher_is_better: bool,
    formatter,
    standing_highlight: StandingHighlight = "",
) -> MatchupCell:
    change = _change_direction(before, after, higher_is_better=higher_is_better)
    before_display = formatter(before) if before is not None else "—"
    after_display = formatter(after) if after is not None else "—"
    if change == "same":
        display = after_display
    elif change == "none":
        display = after_display
    else:
        display = f"{before_display} → {after_display}"

    css_class = ""
    if change == "up":
        css_class = "matchup-cell--up"
    elif change == "down":
        css_class = "matchup-cell--down"
    if standing_highlight == "overtook":
        css_class = "matchup-cell--overtook"
    elif standing_highlight == "overtaken":
        css_class = "matchup-cell--overtaken"

    return MatchupCell(
        display=display,
        change=change,
        css_class=css_class,
        standing_highlight=standing_highlight,
    )


def _rank_delta_cell(
    before: int | None,
    after: int | None,
    *,
    standing_highlight: StandingHighlight = "",
) -> MatchupCell:
    if before is None and after is None:
        change: ChangeDirection = "same"
    elif before is None and after is not None:
        change = "up"
    elif before is not None and after is None:
        change = "down"
    elif before == after:
        change = "same"
    elif after < before:
        change = "up"
    else:
        change = "down"

    before_display = _format_rank(before)
    after_display = _format_rank(after)
    if change == "same":
        display = after_display
    else:
        display = f"{before_display} → {after_display}"

    css_class = ""
    if change == "up":
        css_class = "matchup-cell--up"
    elif change == "down":
        css_class = "matchup-cell--down"
    if standing_highlight == "overtook":
        css_class = "matchup-cell--overtook"
    elif standing_highlight == "overtaken":
        css_class = "matchup-cell--overtaken"

    return MatchupCell(
        display=display,
        change=change,
        css_class=css_class,
        standing_highlight=standing_highlight,
    )


def _this_game_score_row(results, *, low_wins: bool) -> MatchupStatRow:
    scores = [result.score for result in results]
    if len(scores) >= 2 and len(set(scores)) > 1:
        best = min(scores) if low_wins else max(scores)
        worst = max(scores) if low_wins else min(scores)
    else:
        best = worst = None

    cells: list[MatchupCell] = []
    for result in results:
        css_class = ""
        if best is not None and result.score == best:
            css_class = "matchup-cell--up"
        elif worst is not None and result.score == worst:
            css_class = "matchup-cell--down"
        cells.append(
            MatchupCell(
                display=_format_score(result.score),
                css_class=css_class,
            )
        )
    return MatchupStatRow(label="This game score", cells=tuple(cells))


def _this_game_place_row(results) -> MatchupStatRow:
    placements = [
        result.placement for result in results if result.placement is not None
    ]
    if len(placements) >= 2 and len(set(placements)) > 1:
        best = min(placements)
        worst = max(placements)
    else:
        best = worst = None

    cells: list[MatchupCell] = []
    for result in results:
        css_class = ""
        if result.placement is not None:
            if best is not None and result.placement == best:
                css_class = "matchup-cell--up"
            elif worst is not None and result.placement == worst:
                css_class = "matchup-cell--down"
        cells.append(
            MatchupCell(
                display=_display_place(result.placement),
                css_class=css_class,
            )
        )
    return MatchupStatRow(label="Place", cells=tuple(cells))


def _place_pct_row(
    players,
    after_place_pct: dict[int, float | None],
) -> MatchupStatRow:
    return MatchupStatRow(
        label="Place %",
        cells=tuple(
            _after_value_cell(
                after_place_pct.get(player.pk),
                formatter=_format_pct,
            )
            for player in players
        ),
    )


def _this_game_result_row(results) -> MatchupStatRow:
    cells: list[MatchupCell] = []
    for result in results:
        css_class = ""
        if result.result == GameParticipantResult.Result.WIN:
            css_class = "matchup-cell--up"
        elif result.result == GameParticipantResult.Result.LOSS:
            css_class = "matchup-cell--down"
        cells.append(
            MatchupCell(
                display=result.get_result_display(),
                css_class=css_class,
            )
        )
    return MatchupStatRow(label="This game result", cells=tuple(cells))


def _leaderboard_rows(
    players,
    before_ranked,
    after_ranked,
    before_standings,
    after_standings,
    standing_highlights,
    *,
    show_losses: bool,
) -> list[MatchupStatRow]:
    rows: list[MatchupStatRow] = []

    rows.append(
        MatchupStatRow(
            label="Leaderboard rank",
            cells=tuple(
                _rank_delta_cell(
                    (
                        before_ranked[player.pk].rank
                        if player.pk in before_ranked
                        else None
                    ),
                    after_ranked[player.pk].rank if player.pk in after_ranked else None,
                    standing_highlight=standing_highlights.get(player.pk, ""),
                )
                for player in players
            ),
        )
    )

    metric_rows = [
        ("Rank score", "rank_score", True),
        ("Games played", "games_played", True),
        ("Wins", "wins", True),
    ]
    if show_losses:
        metric_rows.append(("Losses", "losses", False))
    metric_rows.append(("Win %", "win_pct", True))

    for label, field, higher_is_better in metric_rows:
        formatter = _format_pct if field == "win_pct" else _format_weighted
        if field == "rank_score":
            formatter = _format_score
        rows.append(
            MatchupStatRow(
                label=label,
                cells=tuple(
                    (
                        _after_value_cell(
                            (
                                getattr(after_standings.get(player.pk), field, None)
                                if after_standings.get(player.pk)
                                else None
                            ),
                            formatter=formatter,
                        )
                        if label == "Games played"
                        else _delta_cell(
                            (
                                getattr(before_standings.get(player.pk), field, None)
                                if before_standings.get(player.pk)
                                else None
                            ),
                            (
                                getattr(after_standings.get(player.pk), field, None)
                                if after_standings.get(player.pk)
                                else None
                            ),
                            higher_is_better=higher_is_better,
                            formatter=formatter,
                        )
                    )
                    for player in players
                ),
            )
        )

    return rows


def _head_to_head_rows(
    players, before_stats, after_stats, *, show_losses: bool
) -> list[MatchupStatRow]:
    rows: list[MatchupStatRow] = []
    metrics = [
        ("Together games", "games_played", True),
        ("Together wins", "wins", True),
        ("Together ties", "ties", True),
    ]
    if show_losses:
        metrics.append(("Together losses", "losses", False))

    for label, field, higher_is_better in metrics:
        rows.append(
            MatchupStatRow(
                label=label,
                cells=tuple(
                    (
                        _after_value_cell(
                            (
                                getattr(after_stats.get(player.pk), field, 0)
                                if after_stats.get(player.pk)
                                else 0
                            ),
                            formatter=lambda value: str(int(value)),
                        )
                        if label == "Together games"
                        else _delta_cell(
                            (
                                getattr(before_stats.get(player.pk), field, 0)
                                if before_stats.get(player.pk)
                                else 0
                            ),
                            (
                                getattr(after_stats.get(player.pk), field, 0)
                                if after_stats.get(player.pk)
                                else 0
                            ),
                            higher_is_better=higher_is_better,
                            formatter=lambda value: str(int(value)),
                        )
                    )
                    for player in players
                ),
            )
        )
    return rows


def _filter_games_through_game(games_qs, game: Game, *, include_game: bool):
    if include_game:
        return games_qs.filter(
            Q(played_on__lt=game.played_on)
            | Q(played_on=game.played_on, pk__lte=game.pk)
        )
    return games_qs.filter(
        Q(played_on__lt=game.played_on) | Q(played_on=game.played_on, pk__lt=game.pk)
    )


def _head_to_head_games_qs(game: Game, players, *, include_game: bool):
    player_ids = [player.pk for player in players]
    qs = Game.objects.filter(
        group=game.group,
        game_type_code=game.game_type_code,
    )
    qs = _filter_games_through_game(qs, game, include_game=include_game)
    return qs.annotate(
        matched_players=Count(
            "participant_results__player",
            filter=Q(participant_results__player_id__in=player_ids),
            distinct=True,
        ),
        total_players=Count("participant_results__player", distinct=True),
    ).filter(matched_players=len(player_ids), total_players=len(player_ids))


def _head_to_head_stats(game: Game, players, *, include_game: bool):
    stats = build_game_list_stats(
        games_qs=_head_to_head_games_qs(game, players, include_game=include_game),
        game_type_code=game.game_type_code,
    )
    if stats is None:
        return {}
    return {row.player.pk: row for row in stats.players}
