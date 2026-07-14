from __future__ import annotations

from datetime import date
from typing import Any

from leaderlodge.games.game_size import available_game_sizes, resolve_game_size
from leaderlodge.games.models import Game
from leaderlodge.insights.tools.compare import compare_players
from leaderlodge.insights.tools.head_to_head import query_head_to_head
from leaderlodge.insights.tools.hall_of_fame import query_hall_of_fame
from leaderlodge.insights.tools.locations import resolve_location_for_group
from leaderlodge.insights.tools.loss_leaders import query_loss_leaders
from leaderlodge.insights.tools.placements import query_placement_leaders
from leaderlodge.insights.tools.players import (
    build_ask_player_roster,
    normalize_player_query,
    resolve_player_query,
)
from leaderlodge.insights.tools.scope import AskScope
from leaderlodge.insights.tools.standings import (
    list_game_types,
    query_date_range_leaderboard,
    query_leaderboard,
    query_location_leaderboard,
    query_player_detail,
)
from leaderlodge.insights.tools.teams import query_team_pairings
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
            "query_loss_leaders": self._query_loss_leaders,
            "compare_players": self._compare_players,
            "query_date_range_leaderboard": self._query_date_range_leaderboard,
            "query_location_leaderboard": self._query_location_leaderboard,
            "query_team_pairings": self._query_team_pairings,
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
        raw_preset = arguments.get("period_preset")
        raw_start = arguments.get("start_date")
        raw_end = arguments.get("end_date")
        if (
            raw_year is None
            and raw_month is None
            and raw_preset is None
            and raw_start is None
            and raw_end is None
        ):
            return self.scope.period

        years, months_by_year = available_leaderboard_periods(
            self.scope.group,
            game_type_code,
        )
        return resolve_leaderboard_period(
            raw_year=str(raw_year or ""),
            raw_month=str(raw_month or ""),
            raw_preset=str(raw_preset or ""),
            raw_start_date=str(raw_start or ""),
            raw_end_date=str(raw_end or ""),
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

    def _parse_iso_date(self, raw: object, field_name: str) -> date:
        try:
            return date.fromisoformat(str(raw).strip())
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError(f"{field_name} must be YYYY-MM-DD.") from exc

    def _resolve_player_ids_list(self, arguments: dict[str, Any]) -> list[int]:
        raw_ids = arguments.get("player_ids")
        raw_queries = arguments.get("player_queries")
        if raw_ids is not None and raw_queries is not None:
            raise ToolExecutionError("Provide player_ids or player_queries, not both.")

        player_ids: list[int] = []
        if raw_queries is not None:
            if not isinstance(raw_queries, list):
                raise ToolExecutionError("player_queries must be a list of names.")
            if len(raw_queries) < 2 or len(raw_queries) > 5:
                raise ToolExecutionError("player_queries must include 2 to 5 players.")
            for query in raw_queries:
                player_ids.append(
                    self._resolve_player_id_from_args(
                        {"player_query": str(query)},
                        prefix="",
                    )
                )
            return player_ids

        if raw_ids is None:
            raise ToolExecutionError("player_ids or player_queries is required.")
        if not isinstance(raw_ids, list):
            raise ToolExecutionError("player_ids must be a list of integers.")
        if len(raw_ids) < 2 or len(raw_ids) > 5:
            raise ToolExecutionError("player_ids must include 2 to 5 players.")
        for raw_id in raw_ids:
            try:
                player_id = int(raw_id)
            except (TypeError, ValueError) as exc:
                raise ToolExecutionError("player_ids must be integers.") from exc
            if not self.scope.group.players.filter(pk=player_id).exists():
                raise ToolExecutionError(
                    f"player_id {player_id} not found in this group."
                )
            player_ids.append(player_id)
        return player_ids

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

    def _query_loss_leaders(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        return query_loss_leaders(
            self.scope.group,
            game_type_code=game_type_code,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )

    def _compare_players(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        player_ids = self._resolve_player_ids_list(arguments)
        return compare_players(
            self.scope.group,
            player_ids=player_ids,
            game_type_code=game_type_code,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
        )

    def _query_date_range_leaderboard(
        self, arguments: dict[str, Any]
    ) -> dict[str, Any]:
        from leaderlodge.leaderboards.period import (
            PERIOD_PRESET_CODES,
            dates_for_period_preset,
        )

        game_type_code = self._resolve_game_type_code(arguments)
        preset = str(arguments.get("period_preset") or "").strip()
        if preset:
            if preset not in PERIOD_PRESET_CODES:
                raise ToolExecutionError(
                    "period_preset must be today, yesterday, last_7_days, "
                    "last_weekend, or last_week."
                )
            bounds = dates_for_period_preset(preset)
            if bounds is None:
                raise ToolExecutionError("Invalid period_preset.")
            start_date, end_date = bounds
        else:
            start_date = self._parse_iso_date(arguments.get("start_date"), "start_date")
            end_date = self._parse_iso_date(arguments.get("end_date"), "end_date")
            if start_date > end_date:
                raise ToolExecutionError("start_date must be on or before end_date.")
        return query_date_range_leaderboard(
            self.scope.group,
            game_type_code=game_type_code,
            start_date=start_date,
            end_date=end_date,
            period_preset=preset or None,
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )

    def _query_location_leaderboard(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        try:
            location = resolve_location_for_group(
                self.scope.group,
                location_id=arguments.get("location_id"),
                location_query=arguments.get("location_query"),
            )
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc

        return query_location_leaderboard(
            self.scope.group,
            game_type_code=game_type_code,
            location_id=location.pk,
            location_name=location.name,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )

    def _query_team_pairings(self, arguments: dict[str, Any]) -> dict[str, Any]:
        game_type_code = self._resolve_game_type_code(arguments)
        return query_team_pairings(
            self.scope.group,
            game_type_code=game_type_code,
            period=self._resolve_period(arguments, game_type_code),
            game_size=self._resolve_game_size(arguments, game_type_code),
            limit=self._resolve_limit(arguments),
        )
