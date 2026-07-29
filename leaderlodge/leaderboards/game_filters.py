from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from leaderlodge.games.features import (
    apply_feature_selections_to_results_qs,
    feature_summary_labels,
    leaderboard_fields_to_selections,
    leaderboard_filter_rows,
    resolve_feature_selections,
    selections_to_leaderboard_fields,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet


@dataclass(frozen=True)
class LeaderboardGameFilters:
    score_type: str | None = None
    double_game: bool | None = None
    half_game: bool | None = None

    def is_active(self) -> bool:
        return bool(self.as_selections())

    def as_selections(self) -> dict[str, str]:
        return leaderboard_fields_to_selections(
            score_type=self.score_type,
            double_game=self.double_game,
            half_game=self.half_game,
        )

    def query_params(self) -> dict[str, str]:
        return self.as_selections()


def resolve_leaderboard_game_filters(
    params,
    *,
    game_type_code: str | None,
) -> LeaderboardGameFilters:
    selections = resolve_feature_selections(params, game_type_code=game_type_code)
    fields = selections_to_leaderboard_fields(selections)
    return LeaderboardGameFilters(
        score_type=fields["score_type"],
        double_game=fields["double_game"],
        half_game=fields["half_game"],
    )


def game_filter_context(
    *,
    game_type_code: str | None,
    selected_filters: LeaderboardGameFilters,
) -> dict:
    if not game_type_code:
        return {
            "game_feature_filters": [],
            "game_filter_labels": [],
        }

    selections = selected_filters.as_selections()
    return {
        "game_feature_filters": leaderboard_filter_rows(
            game_type_code=game_type_code,
            selections=selections,
        ),
        "game_filter_labels": feature_summary_labels(
            selections,
            game_type_code=game_type_code,
        ),
    }


def game_filter_summary_labels(
    filters: LeaderboardGameFilters,
    *,
    game_type_code: str,
) -> list[str]:
    return feature_summary_labels(
        filters.as_selections(),
        game_type_code=game_type_code,
    )


def apply_game_filters_to_results_qs(
    results_qs: QuerySet,
    filters: LeaderboardGameFilters,
    *,
    game_type_code: str,
) -> QuerySet:
    return apply_feature_selections_to_results_qs(
        results_qs,
        filters.as_selections(),
        game_type_code=game_type_code,
    )
