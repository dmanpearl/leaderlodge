from __future__ import annotations

from typing import Any

from leaderlodge.games.game_size import available_game_sizes, resolve_game_size
from leaderlodge.games.models import Game
from leaderlodge.insights.tools.head_to_head import query_head_to_head
from leaderlodge.insights.tools.hall_of_fame import query_hall_of_fame
from leaderlodge.insights.tools.placements import query_placement_leaders
from leaderlodge.insights.tools.players import (
    build_ask_player_roster,
    normalize_player_query,
    resolve_player_query,
)
from leaderlodge.insights.tools.scope import AskScope
from leaderlodge.insights.tools.standings import (
    list_game_types,
    query_leaderboard,
    query_player_detail,
)
from leaderlodge.insights.tools.trends import query_month_leaders, query_rank_trends
from leaderlodge.leaderboards.period import (
    LeaderboardPeriod,
    available_leaderboard_periods,
    resolve_leaderboard_period,
)


class ToolExecutionError(ValueError):
    pass


class ToolExecutor:
    MAX_LIMIT = 20

    def __init__(self, scope: AskScope) -> None:
        self.scope = scope

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers = {
            "list_game_types": self._list_game_types,
            "list_group_players": self._list_group_players,
            "query_leaderboard": self._query_leaderboard,
            "query_placement_leaders": self._query_placement_leaders,
            "query_month_leaders": self._query_month_leaders,
            "query_rank_trends": self._query_rank_trends,
            "query_player_detail": self._query_player_detail,
            "query_head_to_head": self._query_head_to_head,
            "query_hall_of_fame": self._query_hall_of_fame,
        }
        handler = handlers.get(name)
        if handler is None:
            raise ToolExecutionError(f"Unknown tool: {name}")
        return handler(arguments or {})

    def _resolve_game_type_code(self, arguments: dict[str, Any]) -> str:
        raw = str(
            arguments.get("game_type_code") or self.scope.default_game_type_code or ""
        ).strip()
        if raw not in self.scope.available_game_type_codes:
            raise ToolExecutionError("Game type not found for this group.")
        return raw

    def _resolve_period(self, arguments: dict[str, Any], game_type_code: str):
        if arguments.get("all_time"):
            return LeaderboardPeriod.all_time()

        raw_year = arguments.get("year")
        raw_month = arguments.get("month")
        if raw_year is None and raw_month is None:
            return self.scope.period

        years, months_by_year = available_leaderboard_periods(
            self.scope.group,
            game_type_code,
        )
        return resolve_leaderboard_period(
            raw_year=str(raw_year or ""),
            raw_month=str(raw_month or ""),
            available_years=years,
            months_by_year=months_by_year,
        )

    def _resolve_game_size(self, arguments: dict[str, Any], game_type_code: str):
        raw = arguments.get("game_size")
        if raw is None:
            return None
        options = available_game_sizes(
            Game.objects.filter(
                group=self.scope.group,
                game_type_code=game_type_code,
            )
        )
        resolved = resolve_game_size(str(raw), options)
        if resolved is None:
            raise ToolExecutionError(
                "Game size not found for this group and game type."
            )
        return resolved

    def _resolve_limit(self, arguments: dict[str, Any]) -> int:
        raw = arguments.get("limit", 10)
        try:
            limit = int(raw)
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("limit must be an integer.") from exc
        return max(1, min(limit, self.MAX_LIMIT))

    def _list_game_types(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return list_game_types(self.scope.group)

    def _list_group_players(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return {
            "group_id": self.scope.group.pk,
            "group_name": self.scope.group.name,
            "players": build_ask_player_roster(self.scope.group),
        }

    def _resolve_player_id(self, arguments: dict[str, Any]) -> int:
        return self._resolve_player_id_from_args(arguments, prefix="")

    def _resolve_player_id_from_args(
        self, arguments: dict[str, Any], *, prefix: str
    ) -> int:
        id_key = f"{prefix}id" if prefix else "player_id"
        query_key = f"{prefix}query" if prefix else "player_query"
        raw_id = arguments.get(id_key)
        raw_query = normalize_player_query(str(arguments.get(query_key) or ""))

        if raw_id is not None and raw_query:
            raise ToolExecutionError(f"Provide {id_key} or {query_key}, not both.")

        if raw_query:
            bound_id = self.scope.question_player_bindings.get(raw_query.lower())
            if bound_id is not None:
                return bound_id
            try:
                return resolve_player_query(self.scope.group, raw_query).pk
            except ValueError as exc:
                raise ToolExecutionError(str(exc)) from exc

        try:
            player_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(
                f"{id_key} must be an integer or provide {query_key}."
            ) from exc

        if not self.scope.group.players.filter(pk=player_id).exists():
            raise ToolExecutionError(f"{id_key} {player_id} not found in this group.")
        return player_id

    def _resolve_head_to_head_players(
        self, arguments: dict[str, Any]
    ) -> tuple[int, int]:
        player_a_id = self._resolve_player_id_from_args(arguments, prefix="player_a_")
        player_b_id = self._resolve_player_id_from_args(arguments, prefix="player_b_")
        if player_a_id == player_b_id:
            raise ToolExecutionError("Head-to-head requires two different players.")
        return player_a_id, player_b_id

    def _query_leaderboard(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        return query_leaderboard(
            self.scope.group,
            game_type_code=game_type_code,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )

    def _query_placement_leaders(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        try:
            placement = int(arguments.get("placement"))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("placement must be an integer.") from exc
        if placement < 0 or placement > 9:
            raise ToolExecutionError("placement must be between 0 and 9.")

        return query_placement_leaders(
            self.scope.group,
            game_type_code=game_type_code,
            placement=placement,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )

    def _query_month_leaders(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        try:
            month = int(arguments.get("month"))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("month must be an integer.") from exc
        if month < 1 or month > 12:
            raise ToolExecutionError("month must be between 1 and 12.")

        year = arguments.get("year")
        if year is not None:
            year = int(year)

        metric = str(arguments.get("metric") or "rank_score").strip()
        if metric not in {"rank_score", "wins", "games_played"}:
            raise ToolExecutionError(
                "metric must be rank_score, wins, or games_played."
            )

        return query_month_leaders(
            self.scope.group,
            game_type_code=game_type_code,
            month=month,
            year=year,
            game_size=self._resolve_game_size(arguments, game_type_code),
            metric=metric,
            limit=self._resolve_limit(arguments),
        )

    def _query_rank_trends(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        try:
            days = int(arguments.get("days", 90))
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("days must be an integer.") from exc
        if days < 7 or days > 365:
            raise ToolExecutionError("days must be between 7 and 365.")

        return query_rank_trends(
            self.scope.group,
            game_type_code=game_type_code,
            days=days,
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )

    def _query_player_detail(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        player_id = self._resolve_player_id(arguments)

        return query_player_detail(
            self.scope.group,
            player_id=player_id,
            game_type_code=game_type_code,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
        )

    def _query_head_to_head(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        player_a_id, player_b_id = self._resolve_head_to_head_players(arguments)
        return query_head_to_head(
            self.scope.group,
            game_type_code=game_type_code,
            player_a_id=player_a_id,
            player_b_id=player_b_id,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
        )

    def _query_hall_of_fame(self, arguments: dict[str, Any]) -> dict[str, Any]:
        granularity = str(arguments.get("granularity") or "year").strip()
        if granularity not in {"year", "month"}:
            raise ToolExecutionError("granularity must be year or month.")

        game_type_code = arguments.get("game_type_code")
        if game_type_code is not None:
            game_type_code = str(game_type_code).strip()
            if game_type_code not in self.scope.available_game_type_codes:
                raise ToolExecutionError("Game type not found for this group.")

        return query_hall_of_fame(
            self.scope.group,
            granularity=granularity,
            game_type_code=game_type_code,
            limit=self._resolve_limit(arguments),
        )
