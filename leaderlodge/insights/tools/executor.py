from __future__ import annotations

from typing import Any

from leaderlodge.games.game_size import available_game_sizes, resolve_game_size
from leaderlodge.games.models import Game
from leaderlodge.games.registry import GAME_TYPES
from leaderlodge.insights.tools.placements import query_placement_leaders
from leaderlodge.insights.tools.players import (
    build_ask_player_roster,
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
        raw_id = arguments.get("player_id")
        raw_query = str(arguments.get("player_query") or "").strip()

        if raw_id is not None and raw_query:
            raise ToolExecutionError("Provide player_id or player_query, not both.")

        if raw_query:
            try:
                return resolve_player_query(self.scope.group, raw_query).pk
            except ValueError as exc:
                raise ToolExecutionError(str(exc)) from exc

        try:
            player_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(
                "player_id must be an integer or provide player_query."
            ) from exc

        if not self.scope.group.players.filter(pk=player_id).exists():
            raise ToolExecutionError(
                f"player_id {player_id} not found in this group."
            )
        return player_id

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
